"""PostgreSQL port of YHDP's hash-pinned embeddings and RRF (source c661586).

Exact pgvector search is intentional for the local corpus: no unmeasured ANN tuning.
No model I/O occurs in this repository.
"""
import hashlib
import json
from datetime import timedelta
from uuid import uuid4
from psycopg.types.json import Jsonb
from app.errors import ApiError
from app.repo import turns
from app.chat.retrieval import Found, _passage, _COLUMNS

HASH = "encode(sha256(convert_to(p.text || chr(31) || p.context,'UTF8')),'hex')"


def corpus(conn):
    return conn.execute(f"""select p.id,p.text,p.context,{HASH} as content_hash
        from passage p join document d on d.id=p.document_id where not d.is_synthetic order by p.id""").fetchall()


def enqueue(conn, cfg, model, corpus_version, now):
    conn.execute('select pg_advisory_xact_lock(%s)', (turns.ADMISSION_LOCK,))
    old = conn.execute("select * from ai_turn where kind='index' and payload->>'model'=%s and status in ('queued','running')", (model,)).fetchone()
    if old: return old
    if conn.execute("select count(*) n from ai_turn where status='queued'").fetchone()['n'] >= cfg.waiting:
        raise ApiError(429, 'ai_queue_full', 'Hàng đợi AI đã đầy.')
    tid = uuid4()
    payload = {'model': model, 'corpus_version': corpus_version}
    row = conn.execute("""insert into ai_turn(id,kind,route,idempotency_key,payload_hash,payload,queue_deadline,deadline_at,created_at)
        values (%s,'index','internal:index',%s,%s,%s,%s,%s,%s) returning *""",
        (tid, str(tid), hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(), Jsonb(payload),
         now+timedelta(seconds=cfg.queue_s), now+timedelta(seconds=cfg.turn_s), now)).fetchone()
    conn.execute('insert into ai_outbox(turn_id) values (%s)', (tid,))
    return row


def begin(conn, model, revision, version, dimensions):
    row = conn.execute('select dimensions from embedding_index where model=%s and revision=%s and corpus_version=%s', (model,revision,version)).fetchone()
    if row and row['dimensions'] != dimensions:
        raise ValueError('embedding_dimension_changed')
    conn.execute("""insert into embedding_index(model,revision,corpus_version,dimensions) values (%s,%s,%s,%s)
        on conflict(model,revision,corpus_version) do update set completed_at=null""", (model,revision,version,dimensions))


def store(conn, rows, result, version):
    for row, vector in zip(rows, result.vectors, strict=True):
        # Prevent a late embedding response from being attached to changed content.
        fresh = conn.execute(f'select {HASH} as hash from passage p where p.id=%s', (row['id'],)).fetchone()
        if not fresh or fresh['hash'] != row['content_hash']:
            raise ValueError('corpus_changed_during_index')
        conn.execute("""insert into passage_embedding(passage_id,model,revision,corpus_version,content_hash,embedding)
            values (%s,%s,%s,%s,%s,%s::vector)
            on conflict(passage_id,model,revision,corpus_version) do update
            set content_hash=excluded.content_hash,embedding=excluded.embedding""",
            (row['id'],result.model,result.revision,version,row['content_hash'],json.dumps(vector)))


def ready(conn, model, revision, version):
    metadata = conn.execute('select * from embedding_index where model=%s and revision=%s and corpus_version=%s', (model,revision,version)).fetchone()
    if not metadata or not metadata['completed_at']: return False
    return not conn.execute(f"""select 1 from passage p join document d on d.id=p.document_id
        where not d.is_synthetic and not exists(select 1 from passage_embedding e
        where e.passage_id=p.id and e.model=%s and e.revision=%s and e.corpus_version=%s and e.content_hash={HASH}
        and vector_dims(e.embedding)=%s) limit 1""", (model,revision,version,metadata['dimensions'])).fetchone()


def search(conn, normalised, result, version, module_id=None):
    if not ready(conn, result.model, result.revision, version):
        raise ApiError(503, 'retrieval_index_not_ready', 'Chỉ mục nguồn chưa sẵn sàng. Cần lập lại index.')
    dimension = len(result.vectors[0])
    metadata = conn.execute('select dimensions from embedding_index where model=%s and revision=%s and corpus_version=%s', (result.model,result.revision,version)).fetchone()
    if metadata['dimensions'] != dimension:
        raise ApiError(503, 'retrieval_index_not_ready', 'Kích thước embedding đã thay đổi.')
    scope = '' if module_id is None else 'and p.competency_code=any(select unnest(competency_codes) from module where id=%s)'
    dense = conn.execute(f"""select p.id from passage_embedding e join passage p on p.id=e.passage_id
        join document d on d.id=p.document_id where e.model=%s and e.revision=%s and e.corpus_version=%s
        and not d.is_synthetic and vector_dims(e.embedding)=%s and e.content_hash={HASH}
        and (1-(e.embedding <=> %s::vector))>0 {scope}
        order by e.embedding <=> %s::vector,p.id limit 30""",
        # One vector for the positivity gate and one for ordering; scope is between them.
        [result.model,result.revision,version,dimension,json.dumps(result.vectors[0]), *([module_id] if module_id is not None else []), json.dumps(result.vectors[0])]).fetchall()
    sparse = []
    if normalised.terms:
        sparse = conn.execute(f"""select p.id from passage p join document d on d.id=p.document_id
            where not d.is_synthetic and p.tsv @@ to_tsquery('simple',%s) {scope}
            order by ts_rank_cd(p.tsv,to_tsquery('simple',%s),1) desc,p.id limit 30""",
            [' | '.join(normalised.terms), *([module_id] if module_id is not None else []), ' | '.join(normalised.terms)]).fetchall()
    scores = {}
    for ranking in (dense, sparse):
        for rank, row in enumerate(ranking, 1):
            scores[row['id']] = scores.get(row['id'], 0) + 1/(60+rank)
    ids = sorted(scores, key=lambda pid: (-scores[pid],pid))[:5]
    if not ids: return Found([])
    rows = {r['id']:r for r in conn.execute(f'select {_COLUMNS} from passage p join document d on d.id=p.document_id where p.id=any(%s)', (ids,))}
    return Found([_passage(rows[pid], scores[pid]) for pid in ids])
