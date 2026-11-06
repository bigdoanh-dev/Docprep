"""Durable AI state. Locks shared with lifecycle triggers; all user text is pre-sanitised."""
import hashlib
import json
import uuid
from datetime import timedelta
from psycopg.types.json import Jsonb
from app.errors import ApiError

ADMISSION_LOCK = 71103001
RECOVERY_LOCK = 71103002


def lock_learner(conn, learner_id):
    conn.execute("select pg_advisory_xact_lock(71103, %s)", (learner_id,))


def guard(conn, learner_id, now):
    from app.config import settings
    lock_learner(conn, learner_id)
    learner = conn.execute("select * from learner where id=%s", (learner_id,)).fetchone()
    if not learner or not learner["active"]:
        raise ApiError(403, "forbidden", "Tài khoản không còn hoạt động.")
    from app.repo.consent import has_current_service_consent
    if not has_current_service_consent(conn, learner_id, settings()["consent"]["version"]):
        raise ApiError(403, "consent_required", "Bạn cần đồng ý điều khoản dịch vụ.")
    if conn.execute("""select 1 from exam_attempt where learner_id=%s
                         and submitted_at is null and deadline_at > %s limit 1""", (learner_id, now)).fetchone():
        raise ApiError(409, "ai_during_exam", "Không sử dụng AI khi đang làm bài thi.")
    return learner


def own(conn, learner_id, turn_id):
    row = conn.execute("select * from ai_turn where id=%s and learner_id=%s", (turn_id, learner_id)).fetchone()
    if row is None:
        raise ApiError(404, "turn_not_found", "Không tìm thấy lượt AI.")
    return row


def get(conn, turn_id):
    return conn.execute("select * from ai_turn where id=%s", (turn_id,)).fetchone()


def submit(conn, cfg, learner_id, kind, route, key, raw_payload, payload, now, begin):
    fingerprint = hashlib.sha256(json.dumps(raw_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    # Serialises capacity checks + enqueue sequence with outbox publication; never spans model I/O.
    conn.execute("select pg_advisory_xact_lock(%s)", (ADMISSION_LOCK,))
    guard(conn, learner_id, now)
    old = conn.execute("select * from ai_turn where learner_id=%s and route=%s and idempotency_key=%s",
                       (learner_id, route, key)).fetchone()
    if old:
        if old["payload_hash"] != fingerprint:
            raise ApiError(409, "idempotency_conflict", "Khóa gửi lại đã dùng cho nội dung khác.")
        return old
    if conn.execute("select 1 from ai_turn where learner_id=%s and status in ('queued','running')",
                    (learner_id,)).fetchone():
        raise ApiError(409, "ai_turn_active", "Bạn đã có một lượt AI đang xử lý.")
    waiting = conn.execute("select count(*) n from ai_turn where status='queued'").fetchone()["n"]
    if waiting >= cfg.waiting:
        raise ApiError(429, "ai_queue_full", "Hàng đợi AI đã đầy. Vui lòng thử lại sau.")
    session_id = begin()
    turn_id = uuid.uuid4()
    turn = conn.execute("""insert into ai_turn
        (id,learner_id,session_id,kind,route,idempotency_key,payload_hash,payload,queue_deadline,deadline_at,created_at)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
        (turn_id, learner_id, session_id, kind, route, key, fingerprint, Jsonb(payload),
         now + timedelta(seconds=cfg.queue_s), now + timedelta(seconds=cfg.turn_s), now)).fetchone()
    conn.execute("insert into ai_outbox(turn_id) values (%s)", (turn_id,))
    return turn


def failure(conn, turn_id, status, code, message, fence=None):
    sql = """update ai_turn set status=%s, error=%s, finished_at=now()
             where id=%s and status in ('queued','running')"""
    args = [status, Jsonb({"code": code, "message_vi": message}), turn_id]
    if fence is not None:
        sql += " and fence=%s"
        args.append(fence)
    conn.execute(sql, args)


def snapshot(turn):
    return {"turn_id": str(turn["id"]), "kind": turn["kind"], "session_id": turn["session_id"],
            "turn_status": turn["status"], "result": turn["result"], "error": turn["error"]}


def terminal(turn):
    return turn["status"] not in ("queued", "running")


def final_failure(turn):
    return {"turn_id": str(turn["id"]), "turn_status": turn["status"], "state": None, "message_id": None,
            "error": turn["error"] or {"code": "ai_cancelled", "message_vi": "Lượt AI đã dừng."}}
