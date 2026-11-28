"""Local release snapshots. Real signature verification is an explicit future adapter, never a fake success."""
import json
import os
import re
from pathlib import Path
from uuid import UUID, uuid4
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from app.content_tools import page_maps
from .auth import require, audit
from .service import canonical, sha, tag_view, fail


def dev_only():
    if os.environ.get('APP_ENV') not in ('dev','test'):
        raise RuntimeError('Unsigned content publications are only allowed in explicit dev/test')


class SignatureVerifier:
    def verify(self, manifest, metadata):
        raise RuntimeError('No Lead-approved signature protocol/key configured')


def approved_mapping(conn,taxonomy_version):
    """The approved mapping for the taxonomy a tag was made with.

    Approving a mapping stores it on a new snapshot whose payload equals an existing one, so labels made
    earlier with that payload must find it: own snapshot first, else the single approved mapping recorded for
    the same payload (sha256). Two different approved mappings for one payload are refused, never guessed.
    """
    snap=conn.execute('select * from taxonomy_snapshot where version=%s',(taxonomy_version,)).fetchone()
    if not snap:return {}
    if snap['mapping'].get('approved') and snap['mapping'].get('version'):return snap['mapping']
    found=conn.execute("""select distinct mapping from taxonomy_snapshot where sha256=%s
        and mapping->>'approved'='true' and coalesce(mapping->>'version','')<>''""",(snap['sha256'],)).fetchall()
    if len(found)>1:fail('mapping_ambiguous','Có nhiều mapping đã duyệt khác nhau cho cùng taxonomy.',409)
    return found[0]['mapping'] if found else {}


def derived_pages(row):
    """Printed pages from the checked page profile of the source file, for a scan chunk approved without them.

    The approved location (part of the content hash) is never rewritten: the pages travel next to it in the
    manifest, together with the profile version they came from.
    """
    location=row['location'] or {}
    if row['citation_mode']!='page' or location.get('printed_pages'):return None
    pages=page_maps.printed_pages(row['source_sha256'],location.get('image_indices'))
    return {'printed_pages':pages,'version':page_maps.version(row['source_sha256'])} if pages else None


def export_release(conn,user,version,chunk_ids):
    dev_only();require(user,'publisher')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}',version):
        fail('invalid_version','Version release không hợp lệ.')
    if not chunk_ids or len(chunk_ids)!=len(set(chunk_ids)):
        fail('invalid_selection','Chọn ít nhất một chunk, không lặp.')
    conn.execute('select pg_advisory_xact_lock(7419003)')
    chunks=[]
    for cid in sorted(chunk_ids):
        row=conn.execute('''select c.*,s.*,d.title,d.external_doc_id,d.issuer,d.publication_year,d.source_kind,
            d.citation_mode,r.source_availability,b.report->>'source_sha256' as source_sha256
            from document_chunk c join chunk_state s on s.chunk_id=c.id
            join source_document_revision r on r.id=c.revision_id join source_document d on d.id=r.document_id
            left join content_import_batch b on b.id=r.batch_id
            where c.id=%s for update of s''',(cid,)).fetchone()
        if not row or row['classification_status']!='classified' or row['content_status']!='approved':
            fail('not_publishable','Chunk chưa được xác nhận nhãn và nội dung.',409)
        tag=tag_view(conn,row['confirmed_tag_set_id'])
        mapping=approved_mapping(conn,tag['taxonomy_version'])
        if not mapping.get('approved') or not mapping.get('version'):
            fail('mapping_not_approved','Cần mapping có version được reviewer xác nhận trước khi phát hành.',409)
        decisions=conn.execute('select * from chunk_review_decision where id=any(%s)',
            ([row['classification_decision_id'],row['content_approval_decision_id']],)).fetchall()
        chunks.append({'id':str(cid),'source_chunk_id':row['source_chunk_id'],'revision':str(row['revision_id']),
            'document':{k:row[k] for k in ('title','external_doc_id','issuer','publication_year','source_kind','citation_mode','source_availability')},
            'text':row['text'],'search_text':row['search_text'],'kind':row['kind'],'location':row['location'],
            'source_hash':row['content_sha256'], 'taxonomy_version':tag['taxonomy_version'],
            'classification':{k:tag[k] for k in ('van_de','mien','bloom_ceiling','content_type','population','ly_do')},
            'mapping':mapping,'approvals':json.loads(json.dumps(decisions,default=str))})
        if pages:=derived_pages(row):chunks[-1]['page_map']=pages
    policies={d['policy_version'] for c in chunks for d in c['approvals']}
    policy=next(iter(policies)) if len(policies)==1 else 'mixed-v1'
    manifest={'schema':'content.release.v1','version':version,'trust':'local_dev','policy':policy,'chunks':chunks}
    audit(conn,user['id'],'release_export',version,{'chunks':len(chunks)})
    return {'manifest':manifest,'manifest_sha256':sha(canonical(manifest)),'signature':None}


def load_package(path):
    path=Path(path)
    if path.stat().st_size>128*1024**2:raise ValueError('Release too large')
    package=json.loads(path.read_text(encoding='utf-8'))
    manifest=package['manifest']
    if sha(canonical(manifest))!=package['manifest_sha256']:raise ValueError('Release hash mismatch')
    if manifest['schema']!='content.release.v1' or manifest['trust']!='local_dev' or package.get('signature') is not None:
        raise ValueError('Only explicit unsigned local_dev packages are supported; signature adapter is not configured')
    if not manifest['chunks']:raise ValueError('Empty release')
    return package


def runtime_connect():
    return psycopg.connect(os.environ['PUBLISH_DATABASE_URL'],row_factory=dict_row)


def publish(conn,package,actor):
    dev_only();m=package['manifest'];h=sha(canonical(m))
    if h!=package['manifest_sha256'] or m.get('trust')!='local_dev' or package.get('signature') is not None:
        raise ValueError('Unverified or modified local package')
    conn.execute('select pg_advisory_xact_lock(7419004)')
    old=conn.execute('select * from corpus_release where version=%s',(m['version'],)).fetchone()
    if old:
        if old['manifest_sha256']!=h:raise ValueError('Version already used for a different manifest')
        return {'release_id':str(old['id']),'reused':True}
    rid=uuid4();seen=set()
    conn.execute("insert into corpus_release(id,version,manifest,manifest_sha256,trust,status) values(%s,%s,%s,%s,'local_dev','candidate')",(rid,m['version'],Jsonb(m),h))
    for c in m['chunks']:
        UUID(c['id']);UUID(c['revision'])
        if c['id'] in seen:raise ValueError('Duplicate source chunk')
        seen.add(c['id'])
        if sha(canonical([c['text'],c['location'],c['kind']]))!=c['source_hash']:raise ValueError('Chunk content hash mismatch')
        proofs=c['approvals']
        if not all(any(d['purpose']==p and d['decision']=='accept' and d['chunk_id']==c['id'] for d in proofs) for p in ('classification','content')):
            raise ValueError('Missing approval snapshot')
        primary=[v for v in c['classification']['van_de'] if v['primary']]
        if len(primary)!=1:raise ValueError('Invalid classification')
        mapping=c['mapping']
        if not mapping.get('approved') or not mapping.get('version'):raise ValueError('Mapping is unapproved')
        for issue in c['classification']['van_de']:
            target=mapping.get('issues',{}).get(str(issue['id']))
            if not target or not conn.execute('select 1 from core_issue where id=%s',(target['runtime_issue_id'],)).fetchone():raise ValueError('Issue mapping missing')
        target=mapping['issues'][str(primary[0]['id'])];code=target['competency_code']
        if not conn.execute('select 1 from competency_node where code=%s and core_issue_id=%s',(code,target['runtime_issue_id'])).fetchone():raise ValueError('Competency mapping mismatch')
        for domain in c['classification']['mien']:
            component=mapping.get('domains',{}).get(domain['id'])
            if component is None or not conn.execute('select 1 from exam_competency_component where id=%s',(component,)).fetchone():raise ValueError('Domain mapping missing')
        d=c['document'];did='yhdp:'+c['revision'];pid='yhdp:'+rid.hex+':'+UUID(c['id']).hex
        conn.execute('''insert into document(id,title,edition,demo_label) values(%s,%s,%s,%s) on conflict(id) do nothing''',
            (did,d['title'],str(d.get('publication_year') or ''),'Nguồn local/dev; chưa nghiệm thu corpus ký số'))
        from app.text import unaccent
        loc=c['location'];augmentation=loc.get('augmentation') or {}
        context=augmentation.get('contextual_header') or d['title']+'\n'+' › '.join(loc.get('section_path',[]))
        pages=loc.get('printed_pages') or (c.get('page_map') or {}).get('printed_pages') or [];page=int(pages[0]) if pages and str(pages[0]).isdigit() else None
        article=' › '.join(loc.get('section_path',[])) or loc.get('anchor')
        if augmentation.get('figure_asset'):
            article=context
        conn.execute('''insert into passage(id,document_id,chapter,section,article,page_start,competency_code,content_type,
            text,text_unaccented,corpus_version,context,context_unaccented,release_id)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (pid,did,(loc.get('section_path') or [None])[0],loc.get('anchor'),article,page,code,c['classification']['content_type'],
             c['text'],unaccent(c['text']),m['version'],context,unaccent(context),rid))
        snapshot=c['classification']
        if augmentation:
            snapshot={**snapshot,'augmentation':{**augmentation,'source_chunk_id':c['source_chunk_id']}}
        conn.execute('insert into corpus_release_member values(%s,%s,%s,%s,%s,%s,%s)',
            (rid,pid,c['id'],c['revision'],c['source_hash'],Jsonb(snapshot),Jsonb(proofs)))
    return {'release_id':str(rid),'reused':False,'passages':len(seen)}


def activate(conn,version,actor,reason,channel='local',revoke=False):
    dev_only()
    if not reason.strip():raise ValueError('Activation/revocation reason required')
    conn.execute('select pg_advisory_xact_lock(7419004)')
    conn.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',('corpus:'+version,))
    row=conn.execute('select * from corpus_release where version=%s for update',(version,)).fetchone()
    if not row or row['status']=='revoked':raise ValueError('Release absent or revoked')
    old=conn.execute('select * from corpus_activation where channel=%s for update',(channel,)).fetchone()
    conn.execute('update corpus_release set status=%s where id=%s',('revoked' if revoke else 'ready',row['id']))
    if not revoke:
        conn.execute('''insert into corpus_activation(channel,release_id,generation,actor_ref) values(%s,%s,1,%s)
            on conflict(channel) do update set release_id=excluded.release_id,generation=corpus_activation.generation+1,
            activated_at=now(),actor_ref=excluded.actor_ref''',(channel,row['id'],actor))
    conn.execute('''insert into corpus_activation_event(id,channel,from_release_id,to_release_id,action,actor_ref,reason)
        values(%s,%s,%s,%s,%s,%s,%s)''',(uuid4(),channel,old['release_id'] if old else None,row['id'],'revoke' if revoke else 'activate',actor,reason))
    return {'version':version,'status':'revoked' if revoke else 'ready'}
