"""Findings of the phase 4A review: the version of a question an attempt was served, concurrent
requests, a form retired under an open attempt, measured durations, a client that leaves mid-stream."""
import threading
import time
from datetime import datetime, timedelta, timezone

from app.api.streams import stream_events
from app.repo import content
from app.repo import exams as exams_repo
from app.repo import learners
from app.services import chat as chat_service
from app.services import exams
from app.services.idempotency import run_once
from tests.conftest import _test_conn, answer_all, birth_dose_json, make_wrong_unit_answer

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
FORM = "de-thi-thu-1"
DRAFT_STEM = "BẢN NHÁP CHƯA DUYỆT"
Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"


def retire_and_add_draft(conn, question_id: str) -> None:
    """Version 1 is retired and a version 2 exists as a draft, with other option keys and another source."""
    conn.execute("update question set status = 'retired' where id = %s and version = 1", (question_id,))
    conn.execute(
        """insert into question(id, version, type, stem, options, explanation, rubric, competency_code, core_issue_id,
             exam_competency_component_id, bloom_level, difficulty_label, difficulty_b, n_responses,
             source_passage_ids, status, ai_assisted, author)
           select id, 2, type, %s,
                  (select jsonb_agg(o || jsonb_build_object('key', 'x' || (o->>'key'))) from jsonb_array_elements(options) o),
                  %s, rubric, competency_code, core_issue_id, exam_competency_component_id, bloom_level,
                  difficulty_label, difficulty_b, 0, array['draft-source'], 'draft', true, author
           from question where id = %s and version = 1""", (DRAFT_STEM, DRAFT_STEM, question_id))
    conn.commit()


# ---- only a version that was approved is ever shown or scored ---------------------------------

def test_without_a_recorded_version_only_a_once_approved_version_is_used(conn, learner):
    retire_and_add_draft(conn, "q-dt-01")
    assert content.approved_question(conn, "q-dt-01") is None
    served = content.question_as_served(conn, "q-dt-01", None)
    assert (served["version"], served["status"]) == (1, "retired")
    assert content.question_as_served(conn, "q-dt-01", 1)["version"] == 1
    assert content.question_as_served(conn, "q-dt-01", 2) is None           # the draft, even when asked for by number
    assert content.question_as_served(conn, "nope", None) is None


def test_a_running_attempt_keeps_the_version_it_started_with(learner_api, conn):
    attempt = learner_api.post(f"/v1/exams/{FORM}/attempts", json={}).json()
    first = attempt["questions"][0]
    answer_all(learner_api, attempt)
    retire_and_add_draft(conn, first["id"])
    resumed = learner_api.get(f"/v1/attempts/{attempt['attempt_id']}").json()
    assert resumed["questions"][0] == first and DRAFT_STEM not in str(resumed)
    results = learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit").json()
    assert results["score"] == 10
    row = conn.execute("select question_version from item_response where question_id = %s", (first["id"],)).fetchone()
    assert row["question_version"] == 1
    assert conn.execute("select n_responses from question where id = %s and version = 2",
                        (first["id"],)).fetchone()["n_responses"] == 0


def test_a_finished_attempt_is_reviewed_in_the_version_it_was_answered(learner_api, conn):
    attempt = learner_api.post(f"/v1/exams/{FORM}/attempts", json={}).json()
    answer_all(learner_api, attempt, wrong=1)
    learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    first = attempt["questions"][0]
    retire_and_add_draft(conn, first["id"])
    item = learner_api.get(f"/v1/attempts/{attempt['attempt_id']}/items/{first['id']}").json()
    assert item["stem"] == first["stem"] and item["explanation"] != DRAFT_STEM
    assert [o["key"] for o in item["options"]] == [o["key"] for o in first["options"]]
    card = learner_api.get("/v1/cards/due").json()["items"][0]
    assert card["source_passage_id"] != "draft-source" and DRAFT_STEM not in str(card)


def test_the_remediation_reason_quotes_the_version_that_was_answered(learner_api, conn):
    make_wrong_unit_answer(learner_api)
    retire_and_add_draft(conn, "q-dt-01")
    conn.execute("update unit_session set cursor = cursor + 1")
    conn.commit()
    view = learner_api.get("/v1/units/u-dt-01/next").json()
    assert view["item"]["kind"] == "remediation" and view["item"]["reason"] == "Được thêm vì bạn chọn 5% ở câu trước"


# ---- two requests at once -------------------------------------------------------------------------

def test_two_learners_handing_in_at_once_do_not_deadlock(conn, learner, monkeypatch):
    other = learners.get(conn, learners.create(conn, "HV-OTHER", None, "student", "2027-03-15", 0.9, "Người học khác"))
    orders = {learner["id"]: ["q-dt-07", "q-dt-08"], other["id"]: ["q-dt-08", "q-dt-07"]}
    attempt_ids = {}
    for learner_id, order in orders.items():
        attempt = exams_repo.create_attempt(conn, learner_id, FORM, order, {q: ["a", "b", "c", "d"] for q in order},
                                            {q: 1 for q in order}, NOW, NOW + timedelta(minutes=10), None)
        for question_id in order:
            exams_repo.save_answer(conn, attempt["id"], question_id, "a", False, NOW)
        attempt_ids[learner_id] = attempt["id"]
    conn.commit()

    # Each hand-in pauses after scoring its first question, so both hold one question row and want the other's.
    barrier, waited, real = threading.Barrier(2), threading.local(), exams.record_response

    def paused(*args, **kwargs):
        result = real(*args, **kwargs)
        if not getattr(waited, "done", False):
            waited.done = True
            try:
                barrier.wait(timeout=2)
            except threading.BrokenBarrierError:
                pass
        return result

    monkeypatch.setattr(exams, "record_response", paused)
    errors = []

    def hand_in(who: dict) -> None:
        try:
            with _test_conn() as c:
                exams.submit(c, who, attempt_ids[who["id"]], NOW)
        except Exception as error:  # noqa: BLE001 — the test reports whatever went wrong
            errors.append(error)

    threads = [threading.Thread(target=hand_in, args=(who,)) for who in (learner, other)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert errors == []
    assert conn.execute("select count(*) c from exam_attempt where submitted_at is not null").fetchone()["c"] == 2


def test_a_retry_sent_while_the_first_request_is_running_waits_for_its_answer(conn):
    started, release, calls, results = threading.Event(), threading.Event(), [], {}

    def work() -> dict:
        calls.append(1)
        started.set()
        release.wait(10)
        return {"n": len(calls)}

    def request(name: str) -> None:
        with _test_conn() as c:
            results[name] = run_once(c, "k1", "HV-1", "POST /x", work)

    first = threading.Thread(target=request, args=("first",))
    first.start()
    assert started.wait(10)
    retry = threading.Thread(target=request, args=("retry",))
    retry.start()
    retry.join(1.0)
    retry_waited = retry.is_alive()
    release.set()
    first.join(10)
    retry.join(10)
    assert retry_waited and calls == [1] and results == {"first": {"n": 1}, "retry": {"n": 1}}


def test_two_taps_on_start_open_one_attempt(conn, learner):
    conn.commit()
    first_conn = _test_conn()
    first = exams.start(first_conn, learner, FORM, False, NOW)           # the first tap, not yet committed
    second = {}

    def second_tap() -> None:
        with _test_conn() as c:
            second["attempt_id"] = exams.start(c, learner, FORM, False, NOW)["attempt_id"]

    thread = threading.Thread(target=second_tap)
    thread.start()
    thread.join(1.0)
    first_conn.commit()
    first_conn.close()
    thread.join(10)
    assert second["attempt_id"] == first["attempt_id"]
    assert conn.execute("select count(*) c from exam_attempt").fetchone()["c"] == 1


# ---- a form retired while an attempt is open ------------------------------------------------------

def test_an_open_attempt_survives_its_form_being_retired(learner_api, conn, clock):
    attempt = learner_api.post(f"/v1/exams/{FORM}/attempts", json={}).json()
    answer_all(learner_api, attempt)
    conn.execute("update exam_form set status = 'retired' where id = %s", (FORM,))
    conn.commit()
    assert learner_api.get(f"/v1/attempts/{attempt['attempt_id']}").json()["title"] == "Đề thi thử số 1"
    results = learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    assert results.status_code == 200 and results.json()["score"] == 10
    assert FORM not in [f["id"] for f in learner_api.get("/v1/exams").json()["items"]]
    assert learner_api.post(f"/v1/exams/{FORM}/attempts", json={}).json()["error"]["code"] == "form_not_found"


def test_an_attempt_past_its_deadline_on_a_retired_form_is_still_closed(learner_api, conn, clock):
    learner_api.post(f"/v1/exams/{FORM}/attempts", json={})
    conn.execute("update exam_form set status = 'retired' where id = %s", (FORM,))
    conn.commit()
    clock.advance(minutes=11)
    assert learner_api.get("/v1/home").status_code == 200
    assert learner_api.get("/v1/exams").status_code == 200
    assert conn.execute("select auto_submitted from exam_attempt").fetchone()["auto_submitted"] is True


# ---- measured time is not capped ------------------------------------------------------------------

def test_the_logged_exam_duration_is_the_measured_one(learner_api, conn, clock):
    conn.execute("update exam_form set seconds_per_question = 180 where id = %s", (FORM,))      # a 30-minute form
    conn.commit()
    attempt = learner_api.post(f"/v1/exams/{FORM}/attempts", json={}).json()
    clock.advance(minutes=25)
    assert learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit").json()["duration_s"] == 1500
    logged = conn.execute("select duration_ms from activity_event where kind = 'exam_submitted'").fetchone()
    assert logged["duration_ms"] == 1_500_000


# ---- a client that leaves mid-stream --------------------------------------------------------------

def test_an_answer_is_stored_although_the_client_left_mid_stream(learner_api, fake_gw, conn, learner):
    fake_gw.responses = [birth_dose_json(conn)]
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    session = chat_service.begin_turn(conn, learner, sid, Q, False, NOW)
    conn.commit()
    app = learner_api.app
    pool = app.state.pool
    stream = stream_events(pool.connection, lambda connect: chat_service.answer_events(
        connect, app.state.model_slots, fake_gw, learner, session, Q, False, False, NOW))
    assert next(stream).startswith("event: step")
    stream.close()                                                       # what a disconnect does to the generator
    # the rest of the turn runs on a thread of its own (phase 7A): wait for it to be stored
    query = "select role, state, model_version from chat_message where session_id = %s order by id"
    deadline = time.monotonic() + 15
    while len(conn.execute(query, (sid,)).fetchall()) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    rows = conn.execute(query, (sid,)).fetchall()
    assert rows == [{"role": "user", "state": None, "model_version": None},
                    {"role": "assistant", "state": "answered", "model_version": "fake"}]
    stats = pool.get_stats()
    assert stats["pool_available"] == stats["pool_size"]
