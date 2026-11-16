"""Allowlisted YHDP import. SQLite is authoritative; no code, users or LLM logs are imported."""
import json
import mimetypes
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4
import yaml
from psycopg.types.json import Jsonb
from .auth import audit, require
from .service import canonical, sha, insert_tag

MAX_ARCHIVE = 128 * 1024**2
MAX_EXPANDED = 1024**3
VERSION = 'yhdp-import-v1'


def asset_root():
    return Path(os.environ.get('CONTENT_ASSET_ROOT', str(Path(tempfile.gettempdir())/'docprep-content-assets')))


def store_asset(data):
    h=sha(data);root=asset_root();root.mkdir(parents=True,exist_ok=True)
    target=root/h
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=root,delete=False) as f:
            f.write(data);temp=Path(f.name)
        temp.replace(target)
    return h


def add_taxonomy(conn,payload,mapping=None,reviewer=None):
    mapping=mapping or {}
    if mapping.get('approved'):
        if not reviewer:raise ValueError('Approved mapping needs a reviewer')
        require(reviewer,'reviewer')
        mapping={**mapping,'approved_by':str(reviewer['id'])}
    version='yhdp-'+sha(canonical([payload,mapping]))[:20]
    if conn.execute('select 1 from taxonomy_snapshot where version=%s',(version,)).fetchone():return version
    conn.execute('insert into taxonomy_snapshot values(%s,%s,%s,%s)',(version,Jsonb(payload),sha(canonical(payload)),Jsonb(mapping)))
    for v in payload['van_de']:
        conn.execute('insert into taxonomy_issue values(%s,%s,%s,%s)',(version,v['id'],v['name'],str(v['de_muc'])))
    for d in payload['mien']:
        for v in d['sub']:
            conn.execute('insert into taxonomy_domain values(%s,%s,%s)',(version,v['id'],v['name']))
    return version


class Package:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.stat().st_size>MAX_ARCHIVE:raise ValueError('Archive exceeds 128 MiB')
        self.z=zipfile.ZipFile(self.path)
        if sum(i.file_size for i in self.z.infolist())>MAX_EXPANDED:raise ValueError('Expanded archive exceeds 1 GiB')
        names=self.z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive entry')
        for name in names:
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe archive path')
        self.archive_sha256=sha(self.path.read_bytes())
        self.tmp=tempfile.TemporaryDirectory(prefix='content-import-')
        path=Path(self.tmp.name)/'source.db';path.write_bytes(self.z.read('data/yhdp.db'))
        self.db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True);self.db.row_factory=sqlite3.Row
        self.db.execute('pragma query_only=on')
        for table in ('documents','chunks','chunk_tags','review_items'):
            if not self.db.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone():
                raise ValueError('Required source table absent: '+table)
        self.documents=[dict(r) for r in self.db.execute('select * from documents order by doc_id')]
        self.chunks=[dict(r) for r in self.db.execute('select * from chunks order by doc_id,seq')]
        self.tags=[dict(r) for r in self.db.execute('select * from chunk_tags order by ts')]
        self.taxonomy=yaml.safe_load(self.z.read('data/blueprint/qd51.yaml'))

    def close(self):
        self.db.close();self.z.close();self.tmp.cleanup()

    def report(self):
        hashes={(c['chunk_id'],c['content_hash']) for c in self.chunks}
        orphan=[t for t in self.tags if (t['chunk_id'],t['content_hash']) not in hashes]
        mismatch=[]
        for doc in self.documents:
            name=f"data/derived/{doc['doc_id']}/chunks.jsonl"
            if name not in self.z.namelist():continue
            lines={r['chunk_id']:r for r in map(json.loads,self.z.read(name).decode('utf-8').splitlines())}
            for c in [r for r in self.chunks if r['doc_id']==doc['doc_id']]:
                other=lines.pop(c['chunk_id'],None)
                if not other or c['text']!=other['text'] or json.loads(c['loc'])!=other['loc']:
                    mismatch.append(c['chunk_id'])
            mismatch.extend(lines)
        statuses={}
        for t in self.tags:
            if (t['chunk_id'],t['content_hash']) in hashes:
                v=json.loads(t['tags']).get('review_status','unknown');statuses[v]=statuses.get(v,0)+1
        return {'documents':len(self.documents),'chunks':len(self.chunks),'source_tag_status':statuses,
                'unmatched_tags':orphan,'jsonl_differences':mismatch,'authority':'sqlite',
                'source_availability':'derived_only','archive_sha256':self.archive_sha256}


def apply(conn,package,user,mapping=None,document=None):
    require(user,'editor');mapping=mapping or {}
    report=package.report();namespace='yhdp';mapping_version=sha(canonical(mapping))
    # One transaction per package: interrupted work rolls back; completed retries preserve human decisions.
    conn.execute('select pg_advisory_xact_lock(7419002)')
    # Include selection in identity: importing one document must not mark the whole archive imported.
    importer_version=VERSION+':'+(document or 'all')
    old=conn.execute('''select * from content_import_batch where source_namespace=%s and archive_sha256=%s
        and importer_version=%s and mapping_version=%s''',(namespace,package.archive_sha256,importer_version,mapping_version)).fetchone()
    if old:return {'batch_id':str(old['id']),**old['report'],'reused':True}
    bid=uuid4()
    conn.execute('''insert into content_import_batch(id,source_namespace,archive_sha256,importer_version,mapping_version,status,created_by)
        values(%s,%s,%s,%s,%s,'running',%s)''',(bid,namespace,package.archive_sha256,importer_version,mapping_version,user['id']))
    taxonomy=add_taxonomy(conn,package.taxonomy,mapping,user)
    added=0
    selected=[d for d in package.documents if document is None or d['doc_id']==document]
    if not selected:raise ValueError('Document not in source database')
    for d in selected:
        did=uuid4()
        did=conn.execute('''insert into source_document values(%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict(source_namespace,external_doc_id) do update set title=excluded.title returning id''',
            (did,namespace,d['doc_id'],d['title'],d['issuer'],d['year'],d['kind'],d['citation'])).fetchone()['id']
        chunks=[c for c in package.chunks if c['doc_id']==d['doc_id']]
        artifact=sha(canonical([d,chunks]))
        if conn.execute('select 1 from source_document_revision where document_id=%s and artifact_sha256=%s',(did,artifact)).fetchone():continue
        rev=uuid4();n=conn.execute('select coalesce(max(revision_no),0)+1 n from source_document_revision where document_id=%s',(did,)).fetchone()['n']
        conn.execute('''insert into source_document_revision(id,document_id,revision_no,batch_id,artifact_sha256,parser_version,chunker_version,source_availability)
            values(%s,%s,%s,%s,%s,'yhdp-derived-unknown','yhdp.chunk.v1','derived_only')''',(rev,did,n,bid,artifact))
        prefix=f"data/derived/{d['doc_id']}/"
        for name in package.z.namelist():
            if not name.startswith(prefix) or not name.endswith(('.json','.jsonl','.md','.png','.jpg','.jpeg')):continue
            data=package.z.read(name);key=store_asset(data)
            conn.execute('insert into source_asset values(%s,%s,%s,%s,%s,%s,%s,%s)',
                (uuid4(),rev,name[len(prefix):],'derived',mimetypes.guess_type(name)[0] or 'application/octet-stream',len(data),key,key))
        for c in chunks:
            cid=uuid4();extra=json.loads(c['extra']);loc=json.loads(c['loc'])
            conn.execute('''insert into document_chunk values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (cid,rev,c['chunk_id'],c['seq'],c['kind'],c['text'],c['search_text'],Jsonb(loc),c['tokens'],
                 sha(canonical([c['text'],loc,c['kind']])),c['content_hash'],Jsonb(extra.get('needs_review',[])),Jsonb(extra.get('refs',[]))))
            conn.execute('insert into chunk_state(chunk_id) values(%s)',(cid,))
            tags=[t for t in package.tags if t['chunk_id']==c['chunk_id'] and t['content_hash']==c['content_hash']]
            for t in tags:
                original=json.loads(t['tags']);data={**original,'van_de':original['blueprint']['van_de'],'mien':original['blueprint']['mien']}
                # Imported labels remain proposals even if source claims human approval.
                tid=insert_tag(conn,cid,taxonomy,data,'auto',original=original)
                conn.execute('update chunk_state set proposed_tag_set_id=%s where chunk_id=%s',(tid,cid))
            reasons=['awaiting_confirmation']
            source_review=package.db.execute("select payload from review_items where kind='tag' and ref=?",(c['chunk_id'],)).fetchone()
            if source_review:reasons.extend(json.loads(source_review['payload']).get('reasons',[]))
            for purpose in ('classification','content'):
                conn.execute('insert into chunk_review_task values(%s,%s,%s,%s,%s)',
                    (uuid4(),cid,purpose,'open',Jsonb(reasons if purpose=='classification' else extra.get('needs_review',[]))))
            added+=1
    report={**report,'added_chunks':added,'selected_documents':[d['doc_id'] for d in selected],'taxonomy_version':taxonomy}
    conn.execute("update content_import_batch set status='completed',report=%s where id=%s",(Jsonb(report),bid))
    audit(conn,user['id'],'import',bid,{'chunks':added})
    return {'batch_id':str(bid),**report,'reused':False}
