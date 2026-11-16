import copy
from uuid import uuid4
import pytest
from app.content import publication
from app.content.service import canonical, sha
from app.db import connect
from app.repo import content, corpus, embeddings
from app.chat.retrieval import get_passages
from app.errors import ApiError


def package(conn,version='content-test-a'):
    target=conn.execute('select i.id,n.code from core_issue i join competency_node n on n.core_issue_id=i.id order by i.id limit 1').fetchone()
    domain=conn.execute('select id from exam_competency_component order by id limit 1').fetchone()['id']
    cid=str(uuid4());location={'section_path':['Nguồn kiểm thử'],'anchor':'test'}
    text='Nguồn phát hành phục vụ kiểm tra quyền đọc và truy vết.'
    c={'id':cid,'revision':str(uuid4()),'source_chunk_id':'test#c01','text':text,'search_text':text,'kind':'text',
       'location':location,'source_hash':sha(canonical([text,location,'text'])),
       'document':{'title':'Nguồn kiểm thử','external_doc_id':'test','publication_year':None},
       'classification':{'van_de':[{'id':target['id'],'primary':True}],'mien':[{'id':'1.1'}],'content_type':'khác'},
       'mapping':{'version':'test-v1','approved':True,'issues':{str(target['id']):{'runtime_issue_id':target['id'],'competency_code':target['code']}},'domains':{'1.1':domain}},
       'approvals':[{'purpose':p,'decision':'accept','chunk_id':cid} for p in ('classification','content')]}
    m={'schema':'content.release.v1','version':version,'trust':'local_dev','policy':'human-v1','chunks':[c]}
    return {'manifest':m,'manifest_sha256':sha(canonical(m)),'signature':None}


def test_candidate_hidden_then_active_and_durable_citations(world):
    b,chats,_,url=world
    with connect(url) as conn:
        p=package(conn);r=publication.publish(conn,p,'test-publisher')
        assert publication.publish(conn,p,'test-publisher')['reused'] is True
        pid=conn.execute('select passage_id from corpus_release_member where release_id=%s',(r['release_id'],)).fetchone()['passage_id']
        assert content.passage_view(conn,pid) is None
        assert get_passages(conn,[pid])=={}
        assert content.citations_for(conn,[pid])==[]
        assert all(row['id']!=pid for row in embeddings.corpus(conn))
        assert [row['id'] for row in embeddings.corpus(conn,'content-test-a')]==[pid]
        publication.activate(conn,'content-test-a','operator','Verified local snapshot')
        assert corpus.selected(conn)=='content-test-a'
        assert pid in get_passages(conn,[pid])
        from app.chat.pipeline import _passages_block
        from app.privacy import validate_prompt
        validate_prompt('test',[{'role':'user','content':_passages_block(list(get_passages(conn,[pid]).values()))}])
    assert chats[0].get('/v1/passages/'+pid).status_code==200
    assert b.get('/v1/modules').status_code==200


def test_pin_activation_rollback_revocation_and_late_worker(world):
    _,_,_,url=world
    with connect(url) as conn:
        a=package(conn,'a');publication.publish(conn,a,'operator');publication.activate(conn,'a','operator','first')
        b=package(conn,'b');publication.publish(conn,b,'operator')
        a_pid=conn.execute('select passage_id from corpus_release_member m join corpus_release r on r.id=m.release_id where r.version=%s',('a',)).fetchone()['passage_id']
        b_pid=conn.execute('select passage_id from corpus_release_member m join corpus_release r on r.id=m.release_id where r.version=%s',('b',)).fetchone()['passage_id']
        with corpus.pinned('a'):
            publication.activate(conn,'b','operator','second')
            assert set(get_passages(conn,[a_pid,b_pid]))=={a_pid}
        assert set(get_passages(conn,[a_pid,b_pid]))=={b_pid}
        publication.activate(conn,'a','operator','rollback')
        assert corpus.selected(conn)=='a'
        publication.activate(conn,'a','operator','withdraw',revoke=True)
        with pytest.raises(ApiError,match='corpus_revoked'):corpus.selected(conn)
        with pytest.raises(ApiError,match='corpus_revoked'):corpus.recheck(conn,'a','scripted')


def test_real_model_and_modified_release_fail_closed(world,monkeypatch):
    _,_,_,url=world
    with connect(url) as conn:
        p=package(conn);publication.publish(conn,p,'operator')
        with pytest.raises(ApiError,match='corpus_not_verified'):corpus.recheck(conn,'content-test-a','ollama')
        bad=copy.deepcopy(p);bad['manifest']['chunks'][0]['text']='modified'
        with pytest.raises(ValueError,match='modified'):publication.publish(conn,bad,'operator')
        with monkeypatch.context() as env:
            env.setenv('APP_ENV','production')
            with pytest.raises(RuntimeError,match='dev/test'):publication.activate(conn,'content-test-a','operator','not allowed')


def test_publisher_and_business_cannot_write_outside_their_domains(world):
    _,_,_,url=world
    with connect(url) as conn:
        assert not conn.execute("select has_table_privilege('phase_business','corpus_release','INSERT') allowed").fetchone()['allowed']
        exists=conn.execute("select 1 from pg_roles where rolname='phase_publisher'").fetchone()
        if exists:
            assert not conn.execute("select has_table_privilege('phase_publisher','learner_identity','SELECT') allowed").fetchone()['allowed']
            assert not conn.execute("select has_table_privilege('phase_publisher','item_response','INSERT') allowed").fetchone()['allowed']
