"""Real PostgreSQL workspace tests. Never recreate schema outside a dedicated *_test database."""
import io
import json
import os
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import psycopg
import pytest
from fastapi.testclient import TestClient
from app.content import auth, db, importer, service, publication
from app.errors import ApiError
from app.main_content import create_app
from app.content import baseline


@pytest.fixture
def workspace(monkeypatch,tmp_path):
    url=os.environ['CONTENT_TEST_DATABASE_URL']
    assert urlsplit(url).path.endswith('_test') and urlsplit(url).path.lstrip('/').startswith('content_')
    monkeypatch.setenv('CONTENT_DATABASE_URL',url);monkeypatch.setenv('CONTENT_ASSET_ROOT',str(tmp_path/'assets'))
    monkeypatch.setenv('APP_ENV','test')
    with db.connect() as conn:
        conn.execute('drop schema public cascade');conn.execute('create schema public')
    db.migrate()
    with db.connect() as conn:
        uid=auth.create_user(conn,'reviewer.test','ReviewTest2026!','Reviewer',['editor','reviewer','publisher'])
        editor=auth.create_user(conn,'editor.test','ReviewTest2026!','Editor',['editor'])
    return url,{'id':uid,'roles':['editor','reviewer','publisher']},{'id':editor,'roles':['editor']}


def source_package():
    return importer.Package(os.environ['CONTENT_TEST_SOURCE'])


def load(conn,user,doc='qd2760',mapping=None):
    p=source_package()
    try:return importer.apply(conn,p,user,mapping,doc)
    finally:p.close()


def test_import_idempotency_current_hash_and_no_learner_data(workspace):
    _,user,_=workspace
    with db.connect() as conn:
        report=load(conn,user,doc=None)
        assert report['added_chunks']==477
        assert report['source_tag_status']=={'auto':171,'review':306}
        assert len(report['unmatched_tags'])==2
        assert conn.execute("select count(*) n from chunk_state where classification_status='classified'").fetchone()['n']==0
        assert load(conn,user,doc=None)['reused'] is True
        assert conn.execute('select count(*) n from document_chunk').fetchone()['n']==477
        tables={r['tablename'] for r in conn.execute("select tablename from pg_tables where schemaname='public'")}
        assert not tables & {'learner','users','mcq_attempts','revision_cards','chat_message'}
        assert conn.execute('select count(*) n from content_user').fetchone()['n']==2


def test_original_rechunk_is_a_new_pending_revision(workspace, tmp_path):
    from docx import Document
    from app.content.rechunk_import import apply
    from app.content_tools.rechunk import build, registry

    _, user, _ = workspace
    original = tmp_path / 'qd2760.docx'
    word = Document()
    word.add_heading('Đề mục thử nghiệm', level=1)
    word.add_paragraph('Nội dung được lấy từ tài liệu thử nghiệm và cần người biên tập duyệt.')
    word.save(original)
    source = registry(Path(os.environ['CONTENT_TEST_SOURCE']))['qd2760']
    output = tmp_path / 'generated'
    report, chunks = build(source, original, output)
    batch = [(source, original, output, report, chunks)]
    with db.connect() as conn:
        load(conn, user)
        first, = apply(conn, user, batch)
        replay, = apply(conn, user, batch)
        assert first['revision_no'] == 2 and replay == {**first, 'reused': True}
        row = conn.execute("""select s.*, c.location from chunk_state s join document_chunk c on c.id=s.chunk_id
                              where c.revision_id=%s""", (first['revision_id'],)).fetchone()
        assert row['classification_status'] == 'unclassified' and row['content_status'] == 'pending'
        assert row['location']['augmentation']['parent_id'] == chunks[0]['location']['augmentation']['parent_id']
        assert conn.execute('select count(*) n from chunk_review_task where chunk_id=%s', (row['chunk_id'],)).fetchone()['n'] == 2
        assert conn.execute("select count(*) n from source_asset where role='original'").fetchone()['n'] == 1


def test_independent_decisions_stale_version_and_retries(workspace):
    _,user,_=workspace
    with db.connect() as conn:
        load(conn,user)
        cid=conn.execute('select id from document_chunk order by seq limit 1').fetchone()['id']
        s=service.state(conn,cid)
        body={'row_version':s['row_version'],'purpose':'classification','decision':'accept','comment':'Đã kiểm tra nhãn.'}
        a=service.decide(conn,user,cid,body,'same-key')
        assert service.decide(conn,user,cid,body,'same-key')==a
        s=service.state(conn,cid);assert s['classification_status']=='classified' and s['content_status']=='pending'
        with pytest.raises(ApiError,match='version_conflict'):service.decide(conn,user,cid,{**body,'purpose':'content'},'stale')
        b={**body,'row_version':s['row_version'],'purpose':'content'}
        service.decide(conn,user,cid,b,'approve-content')
        assert service.state(conn,cid)['content_status']=='approved'
        s=service.state(conn,cid)
        service.decide(conn,user,cid,{**b,'row_version':s['row_version'],'decision':'revise','comment':'Phát hiện lỗi bảng.'},'revise-content')
        assert service.state(conn,cid)['content_approval_decision_id'] is None
        assert conn.execute('select count(*) n from chunk_review_decision where chunk_id=%s',(cid,)).fetchone()['n']==3


def test_role_and_invalid_labels(workspace):
    _,user,editor=workspace
    with db.connect() as conn:
        report=load(conn,user);cid=conn.execute('select id from document_chunk limit 1').fetchone()['id']
        with pytest.raises(ApiError,match='forbidden'):
            service.decide(conn,editor,cid,{'purpose':'content','decision':'accept','comment':'x','row_version':1},'deny')
        t=service.tag_view(conn,service.state(conn,cid)['proposed_tag_set_id']);t['van_de'][0]['id']=999
        with pytest.raises(ApiError,match='invalid_tags'):service.validate_tags(conn,t,report['taxonomy_version'])


def test_six_level_bloom_api_persists_and_exports_explicit_creative_tag(workspace):
    url,user,_=workspace
    with db.connect() as conn:
        load(conn,user,mapping={'approved':True,'version':'TEST-ONLY'})
        cid=str(conn.execute('select id from document_chunk limit 1').fetchone()['id'])
    with TestClient(create_app(url)) as client:
        tokens=client.post('/v1/auth/login',json={'username':'reviewer.test','password':'ReviewTest2026!'}).json()
        h={'Authorization':'Bearer '+tokens['access_token']}
        levels=['Nhớ','Hiểu','Áp dụng','Phân tích','Đánh giá','Sáng tạo']
        assert client.get('/v1/taxonomies',headers=h).json()['bloom']==levels
        assert client.app.openapi()['components']['schemas']['Bloom']['properties']['level']['enum']==levels
        original=client.get('/v1/chunks/'+cid,headers=h).json()
        t=original['proposed_tags']
        payload={k:t[k] for k in ['van_de','mien','bloom_ceiling','content_type','population','ly_do']}
        payload['bloom_ceiling']={'level':'Sáng tạo','conf':0.8}
        body={'row_version':original['row_version'],'taxonomy_version':t['taxonomy_version'],'tags':payload}
        result=client.post('/v1/chunks/'+cid+'/tags',headers={**h,'Idempotency-Key':'creative-tag'},json=body)
        assert result.status_code==200,result.text
        assert client.post('/v1/chunks/'+cid+'/tags',headers={**h,'Idempotency-Key':'creative-tag'},json=body).json()==result.json()
        saved=client.get('/v1/chunks/'+cid,headers=h).json()
        assert saved['proposed_tags']['bloom_ceiling']=={'level':'Sáng tạo','conf':0.8}
        for purpose in ('classification','content'):
            state=client.get('/v1/chunks/'+cid,headers=h).json()
            decision=client.post('/v1/chunks/'+cid+'/decisions',headers={**h,'Idempotency-Key':purpose},
                json={'row_version':state['row_version'],'purpose':purpose,'decision':'accept','comment':'Test fixture only.'})
            assert decision.status_code==200,decision.text
        # The old imported tag is immutable; only a new explicit proposal uses level 6.
        with db.connect() as conn:
            assert service.tag_view(conn,original['proposed_tag_set_id'])['bloom_ceiling']==t['bloom_ceiling']
            exported=publication.export_release(conn,user,'creative-fixture',[cid])
            assert exported['manifest']['chunks'][0]['classification']['bloom_ceiling']['level']=='Sáng tạo'
        payload['bloom_ceiling']={'level':'Không hợp lệ'}
        invalid=client.post('/v1/chunks/'+cid+'/tags',headers={**h,'Idempotency-Key':'bad-bloom'},json=body)
        assert invalid.status_code==422
        with db.connect() as conn:
            assert conn.execute('select count(*) n from chunk_tag_set where chunk_id=%s',(cid,)).fetchone()['n']==2


def test_bloom_migration_preserves_five_level_history_and_runs_again(workspace):
    _,user,_=workspace
    with db.connect() as conn:
        load(conn,user)
        before=conn.execute('select id,bloom_ceiling from chunk_tag_set order by id').fetchall()
        # Recreate the previous schema constraint on this dedicated test DB only.
        conn.execute('alter table chunk_tag_set drop constraint chunk_tag_set_bloom_ceiling_check')
        conn.execute("alter table chunk_tag_set add constraint chunk_tag_set_bloom_ceiling_check check (bloom_ceiling in ('Nhớ','Hiểu','Áp dụng','Phân tích','Đánh giá'))")
        conn.execute('delete from content_schema_version where version=4')
        with pytest.raises(RuntimeError,match='not ready'):db.check_ready(conn)
    db.migrate()
    db.migrate()
    with db.connect() as conn:
        assert conn.execute('select id,bloom_ceiling from chunk_tag_set order by id').fetchall()==before
        assert conn.execute('select count(*) n from content_schema_version where version=4').fetchone()['n']==1
        t=service.tag_view(conn,before[0]['id'])
        payload={k:t[k] for k in ['van_de','mien','bloom_ceiling','content_type','population','ly_do']}
        payload['bloom_ceiling']={'level':'Sáng tạo'}
        tid=service.insert_tag(conn,t['chunk_id'],t['taxonomy_version'],payload,actor=user['id'])
        assert service.tag_view(conn,tid)['bloom_ceiling']['level']=='Sáng tạo'
        # Direct SQL cannot bypass the supported taxonomy, even with the owner role.
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute("insert into chunk_tag_set select (jsonb_populate_record(null::chunk_tag_set, to_jsonb(t)||jsonb_build_object('id',%s::text,'bloom_ceiling','Không hợp lệ'))).* from chunk_tag_set t where id=%s",(str(uuid4()),tid))


def test_publication_requires_both_approvals_and_mapping(workspace):
    _,user,_=workspace
    with db.connect() as conn:
        load(conn,user);cid=conn.execute('select id from document_chunk limit 1').fetchone()['id']
        with pytest.raises(ApiError,match='not_publishable'):publication.export_release(conn,user,'test',[str(cid)])
        for purpose in ('classification','content'):
            v=service.state(conn,cid)['row_version']
            service.decide(conn,user,cid,{'row_version':v,'purpose':purpose,'decision':'accept','comment':'Reviewed source.'},purpose)
        with pytest.raises(ApiError,match='mapping_not_approved'):publication.export_release(conn,user,'test',[str(cid)])


def test_immutable_decision_and_chunk(workspace):
    _,user,_=workspace
    with db.connect() as conn:
        load(conn,user)
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():conn.execute("update document_chunk set text='changed'")


def test_api_auth_roles_assets_and_logout(workspace):
    url,user,_=workspace
    with db.connect() as conn:load(conn,user)
    with TestClient(create_app(url)) as client:
        contract=client.app.openapi()
        assert contract['paths']['/v1/chunks']['get']['security']==[{'ContentAccessToken':[]}]
        assert 'security' not in contract['paths']['/v1/auth/login']['post']
        assert contract['paths']['/v1/chunks']['get']['responses']['422']['content']['application/json']['schema']['$ref'].endswith('/ErrorEnvelope')
        assert client.get('/v1/chunks').status_code==401
        assert client.post('/v1/auth/login',json={'username':'reviewer.test','password':'wrong'}).status_code==401
        login=client.post('/v1/auth/login',json={'username':'reviewer.test','password':'ReviewTest2026!'}).json()
        h={'Authorization':'Bearer '+login['access_token']}
        data=client.get('/v1/chunks',headers=h).json();assert data['total']==180 and data['classified']==0
        cid=data['items'][0]['id'];detail=client.get('/v1/chunks/'+cid,headers=h).json()
        assert detail['source_availability']=='derived_only'
        assert client.get('/v1/assets/'+str(uuid4()),headers=h).status_code==404
        if detail['assets']:assert client.get('/v1/assets/'+detail['assets'][0]['id'],headers=h).status_code==200
        bad={'row_version':detail['row_version'],'purpose':'classification','decision':'accept','comment':'Checked.'}
        r=client.post('/v1/chunks/'+cid+'/decisions',headers={**h,'Idempotency-Key':'api-key'},json=bad)
        assert r.status_code==200,r.text
        assert client.post('/v1/auth/refresh',json={'refresh_token':login['refresh_token']}).status_code==200
        assert client.get('/v1/chunks',headers=h).status_code==401


def test_zip_traversal_is_rejected(tmp_path):
    p=tmp_path/'bad.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','bad')
    with pytest.raises(ValueError,match='Unsafe'):importer.Package(p)


def test_db_url_guard_rejects_learner_database():
    with pytest.raises(RuntimeError):db.validate_url('postgresql://user:password@host/phase1?content_test')


def test_mapping_approval_requires_reviewer(workspace):
    _,user,editor=workspace
    p=source_package()
    try:
        with db.connect() as conn:
            with pytest.raises(ApiError,match='forbidden'):
                importer.add_taxonomy(conn,p.taxonomy,{'approved':True,'version':'v1'},editor)
            v=importer.add_taxonomy(conn,p.taxonomy,{'approved':True,'version':'v1'},user)
            mapping=conn.execute('select mapping from taxonomy_snapshot where version=%s',(v,)).fetchone()['mapping']
            assert mapping['approved_by']==str(user['id'])
    finally:p.close()


def test_new_proposal_clears_classification_without_editing_history(workspace):
    _,user,_=workspace
    with db.connect() as conn:
        load(conn,user);cid=conn.execute('select id from document_chunk limit 1').fetchone()['id']
        service.decide(conn,user,cid,{'row_version':1,'purpose':'classification','decision':'accept','comment':'Confirmed.'},'approve')
        t=service.tag_view(conn,service.state(conn,cid)['proposed_tag_set_id'])
        payload={k:t[k] for k in ['van_de','mien','bloom_ceiling','content_type','population','ly_do']}
        service.propose(conn,user,cid,{'row_version':2,'taxonomy_version':t['taxonomy_version'],'tags':payload},'new-proposal')
        assert service.state(conn,cid)['classification_status']=='unclassified'
        assert conn.execute('select count(*) n from chunk_review_decision where chunk_id=%s',(cid,)).fetchone()['n']==1
        assert conn.execute('select count(*) n from chunk_tag_set where chunk_id=%s',(cid,)).fetchone()['n']==2


def test_login_rate_limit_and_revoked_session(workspace):
    url,_,_=workspace
    with TestClient(create_app(url)) as client:
        for _ in range(5):
            assert client.post('/v1/auth/login',json={'username':'unknown','password':'incorrect'}).status_code==401
        assert client.post('/v1/auth/login',json={'username':'unknown','password':'incorrect'}).status_code==429
    with db.connect() as conn:
        # A distinct direct login bucket, simulating another permitted source address.
        tokens=auth.login(conn,'reviewer.test','ReviewTest2026!','another-test-ip')
        user=auth.authenticate(conn,tokens['access_token'])
        assert 'reviewer' in user['roles']
        conn.execute('update content_token set revoked=true where user_id=%s',(user['id'],))
        with pytest.raises(ApiError,match='unauthenticated'):auth.authenticate(conn,tokens['access_token'])


def test_content_runtime_cannot_ddl_or_change_decisions(workspace):
    with db.connect() as conn:
        conn.execute('set local role content_app')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():conn.execute('create table forbidden_content_ddl(id int)')
        assert not conn.execute("select has_table_privilege('content_app','chunk_review_decision','UPDATE') allowed").fetchone()['allowed']


def test_partial_import_then_all_preserves_existing_revision(workspace):
    _,user,_=workspace
    with db.connect() as conn:
        assert load(conn,user)['added_chunks']==180
        assert load(conn,user,doc=None)['added_chunks']==297
        assert conn.execute('select count(*) n from document_chunk').fetchone()['n']==477
        assert conn.execute('select count(*) n from source_document_revision').fetchone()['n']==3


def test_sqlite_wins_over_jsonl_differences(workspace,monkeypatch):
    _,user,_=workspace;p=source_package()
    original=p.z.read
    def different(name,*args,**kwargs):
        data=original(name,*args,**kwargs)
        if name=='data/derived/qd2760/chunks.jsonl':
            lines=data.decode('utf-8').splitlines();first=json.loads(lines[0]);first['text']='JSONL changed in test'
            lines[0]=json.dumps(first,ensure_ascii=False);return '\n'.join(lines).encode('utf-8')
        return data
    monkeypatch.setattr(p.z,'read',different)
    try:
        with db.connect() as conn:
            r=importer.apply(conn,p,user,document='qd2760')
            assert r['jsonl_differences']
            assert conn.execute('select text from document_chunk order by seq limit 1').fetchone()['text']!='JSONL changed in test'
    finally:p.close()


def test_source_baseline_full_archive_is_explicit_repeatable_and_revisable(workspace):
    url,user,_=workspace;p=source_package()
    try:
        with db.connect() as conn:
            load(conn,user,doc=None,mapping={'approved':True,'version':'TEST-ONLY'})
            preview=baseline.accept(conn,p,user,'Requested temporary development baseline')
            assert preview['eligible']==477 and not preview['applied']
            assert conn.execute('select count(*) n from chunk_review_decision').fetchone()['n']==0
            result=baseline.accept(conn,p,user,'Requested temporary development baseline',True)
            assert result['accepted']==477
            assert baseline.accept(conn,p,user,'Requested temporary development baseline',True)==result
            assert conn.execute('select count(*) n from chunk_review_decision').fetchone()['n']==954
            assert conn.execute("select count(*) n from chunk_review_decision where policy_version='source-baseline-v1'").fetchone()['n']==954
            assert conn.execute("select count(*) n from chunk_state where classification_status='classified' and content_status='approved'").fetchone()['n']==477
            cid=conn.execute('select chunk_id from chunk_state limit 1').fetchone()['chunk_id']
            assert service.chunk_detail(conn,cid)['content_policy']=='source-baseline-v1'
            release=publication.export_release(conn,user,'source-baseline-test',[cid])
            assert release['manifest']['policy']=='source-baseline-v1'
            s=service.state(conn,cid)
            service.decide(conn,user,cid,{'row_version':s['row_version'],'purpose':'content','decision':'revise','comment':'Review later.'},'later-review')
            baseline.accept(conn,p,user,'Requested temporary development baseline',True)
            assert service.state(conn,cid)['content_status']=='needs_revision'
        with TestClient(create_app(url)) as client:
            tokens=client.post('/v1/auth/login',json={'username':'reviewer.test','password':'ReviewTest2026!'}).json()
            listing=client.get('/v1/chunks',headers={'Authorization':'Bearer '+tokens['access_token']}).json()
            assert listing['classified']==477
            assert all(c['classification_policy']=='source-baseline-v1' for c in listing['items'])
    finally:p.close()


def test_source_baseline_preserves_existing_reviews(workspace):
    _,user,_=workspace;p=source_package()
    try:
        with db.connect() as conn:
            load(conn,user)
            cid=conn.execute('select chunk_id from chunk_state limit 1').fetchone()['chunk_id']
            service.decide(conn,user,cid,{'row_version':1,'purpose':'content','decision':'reject','comment':'Keep this decision.'},'reject-first')
            result=baseline.accept(conn,p,user,'Temporary source',True)
            assert result['accepted']==179 and result['preserved']==1
            assert service.state(conn,cid)['content_status']=='rejected'
    finally:p.close()


def test_source_baseline_blocks_unauthorized_and_incomplete_labels(workspace,monkeypatch):
    _,user,editor=workspace;p=source_package()
    try:
        with db.connect() as conn:
            load(conn,user)
            with pytest.raises(ApiError,match='forbidden'):baseline.accept(conn,p,editor,'Temporary',True)
            with monkeypatch.context() as env:
                env.setenv('APP_ENV','production')
                with pytest.raises(RuntimeError,match='dev/test'):baseline.accept(conn,p,user,'Temporary',True)
            conn.execute('update chunk_state set proposed_tag_set_id=null where chunk_id=(select chunk_id from chunk_state limit 1)')
            with pytest.raises(ValueError,match='Missing or edited'):baseline.accept(conn,p,user,'Temporary',True)
            assert conn.execute('select count(*) n from chunk_review_decision').fetchone()['n']==0
    finally:p.close()
