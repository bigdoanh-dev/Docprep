"""Bounded workers owned by Chat lifespan. No request thread owns a turn."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
import logging
import threading
import time
import uuid

import redis
from psycopg.types.json import Jsonb
from app import events
from app.chat import pipeline, trace
from app.config import settings
from app.errors import ApiError
from app.gateway import GatewayError
from app.ollama_gateway import ModelCallUncertain, OllamaGateway
from app.privacy import clean_tree, validate_prompt
from app.repo import turns, chat, content, responses, units, practice
from app.services import suggestions, hints
from app.services.chat import _summary
from app.services.responses import require_question
from app.engine.hint import usable, pointer

log = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


class TurnStopped(Exception):
    pass


class TurnGateway:
    """Every invocation has a durable reservation before it can reach a provider."""
    def __init__(self, worker, turn):
        self.worker, self.turn = worker, turn

    def complete(self, task, system, messages, prompt_version):
        try:
            validate_prompt(system, messages)
        except GatewayError as exc:
            raise TurnStopped("prompt_identifiers_blocked") from exc
        return self._invoke('complete', task, system, messages, prompt_version)

    def embed(self, texts):
        return self._invoke('embed', texts)

    def _invoke(self, method, *args):
        w, turn = self.worker, self.turn
        gateway = w.gateway_factory()
        call_id, resource = uuid.uuid4(), getattr(gateway, 'resource', 'scripted')
        while True:
            w.check(turn)
            # The recovery mutex prevents a Redis rebuild between slot reservation and DB commit.
            with w.pool.connection() as conn:
                conn.execute("select pg_advisory_xact_lock(%s)", (turns.RECOVERY_LOCK,))
                if turn['learner_id'] is not None:
                    turns.guard(conn, turn["learner_id"], utcnow())
                current = turns.get(conn, turn["id"])
                if not current or current["status"] != "running" or current["fence"] != turn["fence"]:
                    raise TurnStopped("ai_cancelled")
                if not w.coord.slot(resource, call_id, w.owner):
                    acquired = False
                else:
                    acquired = True
                    try:
                        conn.execute("insert into ai_model_call(id,turn_id,resource,owner) values (%s,%s,%s,%s)",
                                     (call_id, turn["id"], resource, w.owner))
                        conn.execute("update ai_turn set model_started=true where id=%s", (turn["id"],))
                    except Exception:
                        w.coord.release_slot(resource, call_id)
                        raise
            if acquired:
                break
            time.sleep(0.1)
        known_finished = True  # cancellation before dispatch cannot leave a remote invocation
        try:
            w.check(turn)
            try:
                known_finished = False
                kwargs = {'deadline': turn['deadline_at']} if isinstance(gateway, OllamaGateway) else {}
                result = getattr(gateway, method)(*args, **kwargs)
                known_finished = True
                return result
            except ModelCallUncertain as exc:
                raise TurnStopped('ai_interrupted') from exc
            except GatewayError as exc:
                known_finished = True  # explicit validation/acknowledged provider rejection
                # Bypass pipeline's content-level GatewayError fallback: infrastructure has its own terminal state.
                raise TurnStopped("model_unavailable") from exc
            except Exception as exc:
                # An unexpected real-adapter failure cannot prove a remote call ended.
                known_finished = not isinstance(gateway, OllamaGateway)
                raise TurnStopped('model_unavailable' if known_finished else 'ai_interrupted') from exc
        finally:
            # A local timeout/disconnect is NOT acknowledgement that remote generation stopped.
            with w.pool.connection() as conn:
                if known_finished:
                    conn.execute("update ai_model_call set ended_at=now(),quarantined=false where id=%s", (call_id,))
                else:
                    conn.execute("update ai_model_call set quarantined=true where id=%s", (call_id,))
            if known_finished:
                try:
                    w.coord.release_slot(resource, call_id)
                except redis.RedisError:
                    pass  # reconciliation removes confirmed released reservations


class ChatWorker:
    def __init__(self, pool, coord, cfg, gateway_factory):
        self.pool, self.coord, self.cfg, self.gateway_factory = pool, coord, cfg, gateway_factory
        self.owner = str(uuid.uuid4())
        self.stop = threading.Event()
        self.draining = False
        self.last_tick = 0.0
        self.executor = ThreadPoolExecutor(max_workers=cfg.active, thread_name_prefix="ai-turn")
        self.jobs = {}
        self.thread = threading.Thread(target=self.loop, name="ai-dispatch", daemon=False)

    def start(self):
        self.reconcile()
        self.thread.start()

    def healthy(self):
        return self.thread.is_alive() and time.monotonic() - self.last_tick < self.cfg.lease_s

    def close(self):
        self.draining = True
        # Keep heartbeats alive while existing turns finish, so another replica does not
        # mistake a graceful shutdown for a dead worker after one lease period.
        deadline = time.monotonic() + self.cfg.turn_s
        while self.thread.is_alive() and any(not f.done() for f in list(self.jobs.values())):
            if time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join()
        self.executor.shutdown(wait=True)

    @contextmanager
    def recovery_connection(self):
        with self.pool.connection() as conn:
            conn.execute("select pg_advisory_lock(%s)", (turns.RECOVERY_LOCK,))
            try:
                yield conn
            finally:
                if conn.info.transaction_status.name == "INERROR":
                    conn.rollback()
                conn.execute("select pg_advisory_unlock(%s)", (turns.RECOVERY_LOCK,))

    def reconcile(self):
        c, cfg = self.coord, self.cfg
        with self.recovery_connection() as conn:
            conn.execute("select pg_advisory_xact_lock(%s)", (turns.ADMISSION_LOCK,))
            epoch = c.epoch()
            rebuild = not epoch or c.r.get(c.key("ready")) != epoch
            if rebuild:
                epoch = c.reset()
            expired = conn.execute("""select * from ai_turn where
                (status='queued' and queue_deadline <= now()) or
                (status='running' and (deadline_at <= now() or heartbeat_at < now() - %s::interval))
                order by seq for update""", (timedelta(seconds=cfg.lease_s),)).fetchall()
            for turn in expired:
                if turn["status"] == "running" and not turn["model_started"] and turn["queue_deadline"] > utcnow():
                    conn.execute("update ai_turn set status='queued',owner=null,fence=fence+1 where id=%s", (turn["id"],))
                    c.release(turn)
                else:
                    status = "interrupted" if turn["model_started"] else "failed"
                    turns.failure(conn, turn["id"], status, "ai_interrupted" if turn["model_started"] else "ai_timeout",
                                  "Lượt AI bị gián đoạn." if turn["model_started"] else "Đã hết thời gian chờ AI.")
                    conn.execute("update ai_model_call set quarantined=true where turn_id=%s and ended_at is null",
                                 (turn["id"],))
            # Sync outbox and processing as one ordered publication pass. Idempotent after every crash window.
            active = conn.execute("select * from ai_turn where status in ('queued','running') order by seq").fetchall()
            active_ids = {str(t['id']) for t in active}
            # Work is bounded by current activity, not the full lifetime history of all chat turns.
            for queue_key in ("queue", "processing"):
                key = c.key(queue_key)
                for tid in c.r.zrange(key, 0, -1):
                    if tid not in active_ids:
                        c.r.zrem(key, tid)
            for key in c.r.scan_iter(match=c.key("learner:*")):
                if c.r.get(key) not in active_ids:
                    c.r.delete(key)
            for turn in active:
                if turn["status"] == "queued":
                    c.r.zrem(c.key("processing"), str(turn["id"]))
                    c.enqueue(turn)
                    conn.execute("update ai_outbox set published_epoch=%s where turn_id=%s and published_epoch is distinct from %s",
                                 (epoch, turn["id"], epoch))
                elif turn["status"] == "running":
                    c.r.zrem(c.key("queue"), str(turn["id"]))
                    c.r.zadd(c.key("processing"), {str(turn["id"]): turn["heartbeat_at"].timestamp()})
                    c.r.set(c.learner_key(turn), str(turn["id"]))
            # Reconstruct GPU reservations even for deleted accounts; never infer a call stopped from a TTL.
            calls = conn.execute("select * from ai_model_call where ended_at is null").fetchall()
            reserved = {str(row["id"]) for row in calls}
            for key in c.r.scan_iter(match=c.key("slots:*")):
                for call_id in c.r.hkeys(key):
                    if call_id not in reserved:
                        c.r.hdel(key, call_id)
            for row in calls:
                c.r.hset(c.key("slots:" + row["resource"]), str(row["id"]), row["owner"])
            for row in conn.execute("select turn_id from ai_purge").fetchall():
                c.purge(row["turn_id"])
                c.r.zrem(c.key("queue"), str(row["turn_id"]))
                c.r.zrem(c.key("processing"), str(row["turn_id"]))
                conn.execute("delete from ai_purge where turn_id=%s", (row["turn_id"],))
            # Commit DB decisions before declaring the Redis epoch usable.
            conn.commit()
            c.r.set(c.key("ready"), epoch)

    def loop(self):
        while not self.stop.is_set():
            try:
                for tid, future in list(self.jobs.items()):
                    if future.done():
                        if future.exception():
                            log.warning("turn_worker_exception", extra={"turn_id": tid,
                                "error_type": type(future.exception()).__name__})
                        del self.jobs[tid]
                    else:
                        with self.pool.connection() as conn:
                            conn.execute("update ai_turn set heartbeat_at=now() where id=%s and owner=%s and status='running'",
                                         (tid, self.owner))
                self.reconcile()
                self.last_tick = time.monotonic()
                if not self.draining and self.cfg.provider != "disabled" and len(self.jobs) < self.cfg.active:
                    with self.pool.connection() as conn:
                        conn.execute("select pg_advisory_xact_lock(%s)", (turns.RECOVERY_LOCK,))
                        conn.execute("select pg_advisory_xact_lock(%s)", (turns.ADMISSION_LOCK,))
                        tid = self.coord.claim(self.coord.epoch(), time.time())
                        turn = conn.execute("""update ai_turn set status='running',owner=%s,fence=fence+1,heartbeat_at=now()
                            where id=%s and status='queued' returning *""", (self.owner, tid)).fetchone() if tid else None
                    if turn:
                        if hasattr(self, "queue_wait_metric"):
                            self.queue_wait_metric.observe((turn['heartbeat_at'] - turn['created_at']).total_seconds())
                        self.jobs[str(turn["id"])] = self.executor.submit(self.run, turn)
            except Exception as exc:
                # Only the exception class is logged; SQL/provider exceptions may contain user data or URLs.
                log.warning("dispatch_unavailable", extra={"error_type": type(exc).__name__})
            self.stop.wait(0.2)

    def check(self, turn):
        with self.pool.connection() as conn:
            if turn['learner_id'] is not None:
                turns.guard(conn, turn["learner_id"], utcnow())
            current = turns.get(conn, turn["id"])
            if not current or current["status"] != "running" or current["owner"] != self.owner or current["fence"] != turn["fence"]:
                raise TurnStopped("ai_cancelled")
            if current["deadline_at"] <= utcnow():
                raise TurnStopped("ai_timeout")

    def prepare(self, conn, turn, learner):
        p = turn["payload"]
        if turn["kind"] == "chat":
            session = chat.own_session(conn, learner["pseudonym_id"], turn["session_id"])
            if not session:
                raise TurnStopped("ai_cancelled")
            if p.get('mode','auto') != 'auto':
                return pipeline.prepare_followup(conn,p['text'],p['mode'],session['id'])
            qid = session.get("question_id")
            if qid and not chat.has_answer(conn, session["id"]):
                question = content.approved_question(conn, qid)
                last = responses.last_for_question(conn, learner["id"], qid)
                if question:
                    return pipeline.prepare_quiz_chat(conn, question, last["chosen"] if last else None, p["text"])
            return pipeline.prepare_answer(conn, p["text"], session["module_id"], p.get("detail", False),
                                           p.get("clarifies_message_id") is not None)
        q = require_question(conn, p["question_id"])
        last = responses.last_for_question(conn, learner["id"], q["id"])
        if last is None:
            raise TurnStopped("not_answered")
        return pipeline.prepare_explain(conn, q, last["chosen"])

    def make_hint(self, turn):
        with self.pool.connection() as conn:
            learner = turns.guard(conn, turn["learner_id"], utcnow())
            q = require_question(conn, turn["payload"]["question_id"])
            if not (units.awaiting_answer(conn, learner["id"], q["id"]) or
                    practice.awaiting_answer(conn, learner["id"], q["id"])):
                raise TurnStopped("hint_unavailable")
            citations = content.citations_for(conn, q["source_passage_ids"])
            by_id = pipeline.get_passages(conn, q["source_passage_ids"])
            passages = [by_id[pid] for pid in q["source_passage_ids"] if pid in by_id]
        text, model = None, None
        if passages:
            model = TurnGateway(self, turn).complete("hint", hints._system(),
                [{"role": "user", "content": hints._user_message(q, passages)}], settings()["prompt_versions"]["hint"])
            reply = pipeline.parse_model_json(model.text) or {}
            if usable(reply.get("hint"), q["options"], q["stem"]):
                text = reply["hint"].strip()
        generated = text is not None
        text = text or (pointer(citations[0]) if citations else "Hãy đọc lại kỹ câu hỏi và từng phương án.")
        return pipeline.ChatOutcome("answered" if generated else "insufficient_evidence", text, citations,
                                    [p.id for p in passages], model), [], generated

    def index_corpus(self, turn):
        from app.repo import embeddings
        gateway = self.gateway_factory()
        if not isinstance(gateway, OllamaGateway) or turn['payload']['model'] != gateway.cfg.embedding:
            raise TurnStopped('index_model_not_configured')
        version = turn['payload']['corpus_version']
        if version != settings()['corpus_version']:
            raise TurnStopped('corpus_version_changed')
        revision = gateway.revisions()[gateway.cfg.embedding]
        with self.pool.connection() as conn:
            snapshot = embeddings.corpus(conn)
            previous = {r['passage_id']:r['content_hash'] for r in conn.execute(
                'select passage_id,content_hash from passage_embedding where model=%s and revision=%s and corpus_version=%s',
                (gateway.cfg.embedding,revision,version))}
        if not snapshot:
            raise TurnStopped('corpus_empty')
        pending = [r for r in snapshot if previous.get(r['id']) != r['content_hash']]
        for start in range(0,len(pending),32):
            self.check(turn)
            batch = pending[start:start+32]
            vectors = TurnGateway(self,turn).embed([clean_tree(r['context']+'\n'+r['text']) for r in batch])
            if vectors.revision != revision:
                raise TurnStopped('embedding_model_changed')
            self.check(turn)
            with self.pool.connection() as conn:
                # Fence before writing derived vectors as well as before terminal commit.
                current = conn.execute('select status,fence from ai_turn where id=%s for update',(turn['id'],)).fetchone()
                if not current or current['status']!='running' or current['fence']!=turn['fence']:
                    raise TurnStopped('ai_cancelled')
                embeddings.begin(conn,vectors.model,revision,version,len(vectors.vectors[0]))
                embeddings.store(conn,batch,vectors,version)
        self.check(turn)
        with self.pool.connection() as conn:
            current = conn.execute('select status,fence from ai_turn where id=%s for update',(turn['id'],)).fetchone()
            if not current or current['status']!='running' or current['fence']!=turn['fence']:
                raise TurnStopped('ai_cancelled')
            actual = embeddings.corpus(conn)
            if [(r['id'],r['content_hash']) for r in snapshot] != [(r['id'],r['content_hash']) for r in actual]:
                raise TurnStopped('corpus_changed_during_index')
            conn.execute('update embedding_index set completed_at=now() where model=%s and revision=%s and corpus_version=%s',
                         (gateway.cfg.embedding,revision,version))
            if not embeddings.ready(conn,gateway.cfg.embedding,revision,version):
                raise TurnStopped('retrieval_index_not_ready')
            result = {'passages':len(snapshot),'embedded':len(pending),'model':gateway.cfg.embedding,
                      'revision':revision,'corpus_version':version}
            conn.execute("update ai_turn set status='completed',finished_at=now(),result=%s where id=%s",(Jsonb(result),turn['id']))

    def run(self, turn):
        try:
            self.check(turn)
            if turn['kind'] == 'index':
                self.index_corpus(turn)
                return
            generated = False
            if turn["kind"] == "hint":
                outcome, steps, generated = self.make_hint(turn)
            else:
                pending = []
                with self.pool.connection() as conn:
                    learner = turns.guard(conn, turn["learner_id"], utcnow())
                    prepared = None
                    for kind, data in self.prepare(conn, turn, learner):
                        if kind == "step":
                            pending.append(("step", data))
                        else:
                            prepared = data
                if self.cfg.provider == 'ollama' and turn['kind'] == 'chat' and turn['payload'].get('mode','auto') == 'auto' and (
                        prepared.task == 'answer' or prepared.outcome and prepared.outcome.state == 'insufficient_evidence'):
                    from app.chat.normalise import normalise
                    from app.repo import embeddings
                    with self.pool.connection() as conn:
                        normalised = normalise(turn['payload']['text'], content.glossary(conn))
                    self.coord.emit(turn['id'], 'status', {'status': 'retrieving'})
                    # Query embedding is model I/O, outside every database context.
                    vector = TurnGateway(self, turn).embed([turn['payload']['text']])
                    self.check(turn)
                    with self.pool.connection() as conn:
                        session = chat.own_session(conn, learner['pseudonym_id'], turn['session_id'])
                        found = embeddings.search(conn, normalised, vector, settings()['corpus_version'], session['module_id'])
                        pending = []
                        for kind, data in pipeline.prepare_answer(conn, turn['payload']['text'], session['module_id'],
                                turn['payload'].get('detail', False), turn['payload'].get('clarifies_message_id') is not None,
                                found=found):
                            if kind == 'step': pending.append(('step', data))
                            else: prepared = data
                for event, data in pending:
                    self.coord.emit(turn["id"], event, data)
                outcome, steps = prepared.outcome, prepared.steps
                if outcome is None:
                    for kind, data in pipeline.generate(TurnGateway(self, turn), prepared):
                        if kind == "done":
                            outcome = data
                        else:
                            self.coord.emit(turn["id"], kind, {"status": data} if kind == "status" else data)
            self.check(turn)
            with self.pool.connection() as conn:
                learner = turns.guard(conn, turn["learner_id"], utcnow())
                current = conn.execute("select * from ai_turn where id=%s for update", (turn["id"],)).fetchone()
                if not current or current["status"] != "running" or current["fence"] != turn["fence"]:
                    raise TurnStopped("ai_cancelled")
                model = outcome.model
                outcome.text = clean_tree(outcome.text)
                mid = chat.add_message(conn, turn["session_id"], "assistant", outcome.text, utcnow(),
                    state=outcome.state, answer_format="text", citations=outcome.citations,
                    retrieved_passage_ids=outcome.retrieved_ids, notice=outcome.notice, trace=trace.stored(steps),
                    claims_checked=outcome.claims_checked, claims_removed=outcome.claims_removed,
                    clarify_options=clean_tree(outcome.clarify_options), searched=outcome.searched,
                    nearest_chapter=outcome.nearest_chapter, model_version=model.model if model else None,
                    prompt_version=model.prompt_version if model else None, corpus_version=settings()["corpus_version"],
                    latency_ms=model.latency_ms if model else None, tokens_in=model.tokens_in if model else None,
                    tokens_out=model.tokens_out if model else None, cost=model.cost if model else None)
                conn.execute("update chat_message set ai_turn_id=%s where id=%s", (turn["id"], mid))
                offers = []
                if turn["kind"] == "chat":
                    try:
                        with conn.transaction():
                            offers = suggestions.after_answer(conn, learner, mid, outcome, utcnow())
                    except Exception:
                        log.warning("suggestions_failed", extra={"turn_id": str(turn["id"])})
                answer = {"text": outcome.text, "citations": outcome.citations, "notice": outcome.notice, "format": "text"}
                final = {"turn_id": str(turn["id"]), "turn_status": "completed", "state": outcome.state,
                         'mode': turn['payload'].get('mode','auto'),
                         "message_id": mid, "format": "text", "trace_summary": _summary(outcome.citations,
                         outcome.claims_checked, outcome.claims_removed), "suggestions": offers,
                         "clarify_options": outcome.clarify_options, "searched": outcome.searched,
                         "nearest_chapter": outcome.nearest_chapter}
                result = {"answer": answer, "final": final}
                if turn["kind"] == "hint":
                    result["hint"] = {"text": outcome.text, "citations": outcome.citations, "generated": generated}
                conn.execute("update ai_turn set status='completed',finished_at=now(),result=%s where id=%s",
                             (Jsonb(result), turn["id"]))
            # Snapshot is durable before either terminal event. Readers can recover the commit/publish gap.
            self.coord.emit(turn["id"], "answer", answer)
            self.coord.emit(turn["id"], "final", final)
        except Exception as exc:
            code = exc.code if isinstance(exc, ApiError) else str(exc) if isinstance(exc, TurnStopped) else "ai_failed"
            with self.pool.connection() as conn:
                turns.failure(conn, turn["id"], 'interrupted' if code == 'ai_interrupted' else "failed", code, "Không thể hoàn thành lượt AI. Vui lòng thử lại.", turn["fence"])
            log.warning("turn_failed", extra={"turn_id": str(turn["id"]), "error_type": type(exc).__name__})
        finally:
            try:
                # An old worker may finish after this same turn was claimed with
                # a newer fence. Serialise with claim/recovery before touching
                # Redis, otherwise it could release the replacement's dispatch lease.
                with self.pool.connection() as conn:
                    conn.execute("select pg_advisory_xact_lock(%s)", (turns.RECOVERY_LOCK,))
                    current = turns.get(conn, turn["id"])
                    if current is None or current["fence"] == turn["fence"]:
                        self.coord.release(turn)
            except Exception:
                pass  # Reconciliation cleans stale dispatch state when dependencies recover.
