"""Content use cases; each caller owns one short transaction."""
import hashlib
import json
from uuid import uuid4
from typing import Literal, get_args
from psycopg.types.json import Jsonb
from app.errors import ApiError
from .auth import audit, require

BloomLevel = Literal['Nhớ','Hiểu','Áp dụng','Phân tích','Đánh giá','Sáng tạo']
BLOOM = get_args(BloomLevel)
TYPES = ('định_nghĩa','dịch_tễ','nguyên_nhân','lâm_sàng','cận_lâm_sàng','chẩn_đoán',
         'chẩn_đoán_phân_biệt','điều_trị','phòng_bệnh','tiên_lượng','quy_trình','khác')
POPULATIONS = ('trẻ_em','thiếu_niên','người_lớn','thai_phụ','người_cao_tuổi','cộng_đồng')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def fail(code, message, status=422):
    raise ApiError(status, code, message)


def once(conn, user, route, key, body, operation):
    if not key or len(key) > 128:
        fail('invalid_key', 'Cần Idempotency-Key dài 1–128 ký tự.')
    conn.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))', (str(user['id'])+route+key,))
    h = sha(canonical(body))
    old = conn.execute('select * from content_operation where actor_id=%s and route=%s and key=%s', (user['id'], route, key)).fetchone()
    if old:
        if old['payload_hash'] != h:
            fail('idempotency_conflict', 'Key đã dùng với nội dung khác.', 409)
        return old['result']
    result = operation()
    conn.execute('insert into content_operation values(%s,%s,%s,%s,%s)', (user['id'], route, key, h, Jsonb(result)))
    return result


def state(conn, cid, version=None):
    row = conn.execute('select * from chunk_state where chunk_id=%s for update', (cid,)).fetchone()
    if not row:
        fail('chunk_not_found', 'Không tìm thấy chunk.', 404)
    if version is not None and row['row_version'] != version:
        fail('version_conflict', 'Chunk đã thay đổi. Hãy tải lại trước khi lưu.', 409)
    return row


def validate_tags(conn, data, taxonomy):
    snap = conn.execute('select version from taxonomy_snapshot where version=%s', (taxonomy,)).fetchone()
    if not snap:
        fail('invalid_taxonomy', 'Không tìm thấy taxonomy.')
    issues, domains = data.get('van_de', []), data.get('mien', [])
    if not 1 <= len(issues) <= 3 or sum(v.get('primary') is True for v in issues) != 1:
        fail('invalid_tags', 'Cần đúng một vấn đề chính và tối đa hai vấn đề phụ.')
    if len({v['id'] for v in issues}) != len(issues) or not 1 <= len(domains) <= 2 or len({v['id'] for v in domains}) != len(domains):
        fail('invalid_tags', 'Vấn đề/miền bị lặp hoặc số miền không hợp lệ.')
    for table, column, values in [('taxonomy_issue','issue_id',issues), ('taxonomy_domain','domain_code',domains)]:
        for value in values:
            if not conn.execute(f'select 1 from {table} where snapshot_version=%s and {column}=%s', (taxonomy,value['id'])).fetchone():
                fail('invalid_tags', 'Nhãn không thuộc taxonomy đã chọn.')
            confidence = value.get('conf')
            if confidence is not None and not 0 <= confidence <= 1:
                fail('invalid_tags', 'Confidence phải từ 0 đến 1.')
    if data.get('bloom_ceiling', {}).get('level') not in BLOOM or data.get('content_type') not in TYPES:
        fail('invalid_tags', 'Bloom hoặc loại nội dung không hợp lệ.')
    if set(data.get('population', [])) - set(POPULATIONS):
        fail('invalid_tags', 'Đối tượng không hợp lệ.')


def insert_tag(conn, cid, taxonomy, data, source='human', actor=None, original=None):
    validate_tags(conn, data, taxonomy)
    tid = uuid4()
    conn.execute('''insert into chunk_tag_set(id,chunk_id,taxonomy_version,source,bloom_ceiling,bloom_confidence,
        content_type,population,rationale,original_payload,created_by) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (tid,cid,taxonomy,source,data['bloom_ceiling']['level'],data['bloom_ceiling'].get('conf'),data['content_type'],
         data.get('population',[]),data.get('ly_do',''),Jsonb(original or data),actor))
    for v in data['van_de']:
        conn.execute('insert into chunk_issue_tag values(%s,%s,%s,%s,%s)',(tid,taxonomy,v['id'],v['primary'],v.get('conf')))
    for v in data['mien']:
        conn.execute('insert into chunk_domain_tag values(%s,%s,%s,%s)',(tid,taxonomy,v['id'],v.get('conf')))
    return tid


def tag_view(conn, tid):
    t = conn.execute('select * from chunk_tag_set where id=%s', (tid,)).fetchone()
    if not t:
        return None
    return {**t, 'van_de':[{'id':v['issue_id'],'primary':v['is_primary'],'conf':v['confidence']} for v in
            conn.execute('select * from chunk_issue_tag where tag_set_id=%s order by is_primary desc,issue_id',(tid,))],
            'mien':[{'id':v['domain_code'],'conf':v['confidence']} for v in
            conn.execute('select * from chunk_domain_tag where tag_set_id=%s order by domain_code',(tid,))],
            'bloom_ceiling':{'level':t['bloom_ceiling'],'conf':t['bloom_confidence']}, 'ly_do':t['rationale']}


def chunk_detail(conn, cid):
    row = conn.execute('''select c.*,s.classification_status,s.content_status,s.row_version,s.proposed_tag_set_id,
        s.confirmed_tag_set_id,cd.policy_version classification_policy,ad.policy_version content_policy,
        d.title,d.external_doc_id,r.source_availability from document_chunk c
        join chunk_state s on s.chunk_id=c.id join source_document_revision r on r.id=c.revision_id
        join source_document d on d.id=r.document_id
        left join chunk_review_decision cd on cd.id=s.classification_decision_id
        left join chunk_review_decision ad on ad.id=s.content_approval_decision_id where c.id=%s''',(cid,)).fetchone()
    if not row:
        fail('chunk_not_found','Không tìm thấy chunk.',404)
    return {**row,'proposed_tags':tag_view(conn,row['proposed_tag_set_id']),
            'confirmed_tags':tag_view(conn,row['confirmed_tag_set_id']),
            'tasks':conn.execute('select * from chunk_review_task where chunk_id=%s order by purpose',(cid,)).fetchall(),
            'decisions':conn.execute('''select d.*,u.display_name from chunk_review_decision d join content_user u on u.id=d.reviewer_id
                where chunk_id=%s order by created_at desc''',(cid,)).fetchall(),
            'assets':conn.execute('select id,asset_key,mime_type from source_asset where revision_id=%s order by asset_key',(row['revision_id'],)).fetchall()}


def propose(conn,user,cid,body,key):
    require(user,'editor')
    def action():
        state(conn,cid,body['row_version'])
        tid=insert_tag(conn,cid,body['taxonomy_version'],body['tags'],actor=user['id'])
        conn.execute("""update chunk_state set proposed_tag_set_id=%s,confirmed_tag_set_id=null,classification_decision_id=null,
            classification_status='unclassified',row_version=row_version+1,updated_at=now() where chunk_id=%s""",(tid,cid))
        conn.execute("update chunk_review_task set status='open',reasons='[\"awaiting_confirmation\"]' where chunk_id=%s and purpose='classification'",(cid,))
        audit(conn,user['id'],'tags_proposed',cid)
        return {'tag_set_id':str(tid),'row_version':body['row_version']+1}
    return once(conn,user,'tags:'+str(cid),key,body,action)


def decide(conn,user,cid,body,key,*,policy_version='human-v1'):
    require(user,'reviewer')
    if policy_version not in ('human-v1','source-baseline-v1'):
        raise ValueError('Unsupported decision policy')
    if policy_version=='source-baseline-v1':
        from .publication import dev_only
        dev_only()
    purpose, decision = body['purpose'],body['decision']
    if purpose not in ('classification','content') or decision not in ('accept','revise','reject'):
        fail('invalid_decision','Quyết định không hợp lệ.')
    if not body.get('comment','').strip():
        fail('comment_required','Cần ghi lý do hoặc nội dung đã kiểm tra.')
    def action():
        s=state(conn,cid,body['row_version']);tid=s['proposed_tag_set_id']
        if purpose=='classification' and decision=='accept':
            if not tid:fail('tags_missing','Chưa có bộ nhãn để xác nhận.',409)
            t=tag_view(conn,tid);validate_tags(conn,t,t['taxonomy_version'])
        task=conn.execute('select id from chunk_review_task where chunk_id=%s and purpose=%s',(cid,purpose)).fetchone()['id']
        did=uuid4()
        conn.execute('''insert into chunk_review_decision(id,task_id,chunk_id,tag_set_id,purpose,decision,reviewer_id,comment,policy_version)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(did,task,cid,tid,purpose,decision,user['id'],body['comment'],policy_version))
        if purpose=='classification':
            conn.execute('''update chunk_state set classification_status=%s,confirmed_tag_set_id=%s,classification_decision_id=%s,
                row_version=row_version+1,updated_at=now() where chunk_id=%s''',
                ('classified' if decision=='accept' else 'unclassified',tid if decision=='accept' else None,did if decision=='accept' else None,cid))
        else:
            conn.execute('''update chunk_state set content_status=%s,content_approval_decision_id=%s,
                row_version=row_version+1,updated_at=now() where chunk_id=%s''',
                ({'accept':'approved','revise':'needs_revision','reject':'rejected'}[decision],did if decision=='accept' else None,cid))
        conn.execute('update chunk_review_task set status=%s where id=%s',('resolved' if decision=='accept' else 'open',task))
        audit(conn,user['id'],'decision:'+purpose,cid,{'decision':decision,'policy_version':policy_version})
        return {'decision_id':str(did),'row_version':body['row_version']+1}
    fingerprint=body if policy_version=='human-v1' else {**body,'policy_version':policy_version}
    return once(conn,user,'decide:'+str(cid),key,fingerprint,action)
