"""Explicit temporary source acceptance for dev/test; never expert verification."""
import json
from . import service
from .auth import require, audit
from .publication import dev_only

POLICY='source-baseline-v1'


def accept(conn,package,user,reason,apply=False):
    dev_only();require(user,'reviewer')
    if not reason.strip() or len(reason)>3000:raise ValueError('Record a reason of 1–3000 characters')
    source={(c['doc_id'],c['chunk_id']):c for c in package.chunks}
    originals={(t['chunk_id'],t['content_hash']):json.loads(t['tags']) for t in package.tags}
    def prepare(lock=False):
        rows=conn.execute('''select c.*,d.external_doc_id,s.row_version,s.proposed_tag_set_id
            from document_chunk c join chunk_state s on s.chunk_id=c.id
            join source_document_revision r on r.id=c.revision_id join source_document d on d.id=r.document_id
            join content_import_batch b on b.id=r.batch_id
            where b.archive_sha256=%s and d.source_namespace='yhdp'
              and r.revision_no=(select max(r2.revision_no) from source_document_revision r2 where r2.document_id=d.id)
            order by c.id'''+(' for update of s' if lock else ''),(package.archive_sha256,)).fetchall()
        if not rows:raise ValueError('Import this exact archive first; no current matching revisions found')
        # Fresh statement after acquiring state locks also sees a reviewer that committed while we waited.
        reviewed={r['chunk_id'] for r in conn.execute('select distinct chunk_id from chunk_review_decision where chunk_id=any(%s)',
                  ([r['id'] for r in rows],))}
        eligible=[]
        for row in rows:
            if row['id'] in reviewed:continue  # Never overwrite a later review, rejection or prior baseline.
            original=source.get((row['external_doc_id'],row['source_chunk_id']))
            if not original or service.sha(service.canonical([original['text'],json.loads(original['loc']),original['kind']]))!=row['content_sha256']:
                raise ValueError('Source chunk differs from the imported snapshot')
            tags=service.tag_view(conn,row['proposed_tag_set_id'])
            if not tags or tags['source']!='auto' or tags['original_payload']!=originals.get((original['chunk_id'],original['content_hash'])):
                raise ValueError('Missing or edited labels; review this chunk individually')
            service.validate_tags(conn,tags,tags['taxonomy_version'])
            eligible.append(row)
        return rows,eligible
    if not apply:
        rows,eligible=prepare()
        return {'policy_version':POLICY,'archive_sha256':package.archive_sha256,'matched':len(rows),
                'eligible':len(eligible),'preserved':len(rows)-len(eligible),'applied':False}
    def action():
        rows,eligible=prepare(True)
        for row in eligible:
            for offset,purpose in enumerate(('classification','content')):
                body={'row_version':row['row_version']+offset,'purpose':purpose,'decision':'accept',
                      'comment':'Chấp nhận tạm theo dữ liệu nguồn data.zip; chưa thẩm định chuyên môn. '+reason}
                service.decide(conn,user,row['id'],body,f'baseline:{package.archive_sha256}:{purpose}',policy_version=POLICY)
        result={'policy_version':POLICY,'archive_sha256':package.archive_sha256,'matched':len(rows),
                'accepted':len(eligible),'preserved':len(rows)-len(eligible),'applied':True}
        audit(conn,user['id'],'source_baseline_accepted',package.archive_sha256,{**result,'reason':reason})
        return result
    return service.once(conn,user,'accept-source-baseline',package.archive_sha256,{'policy_version':POLICY,'reason':reason},action)
