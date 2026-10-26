"""Account deletion: what is erased, what is kept, and that it takes effect at once."""
import pytest

from app.config import settings

TABLES = ("learner", "learner_identity", "consent_record", "item_response", "card", "mastery", "chat_session",
          "chat_message", "error_report", "idempotency_key", "auth_token")


def count(conn, table):
    return conn.execute(f"select count(*) c from {table}").fetchone()["c"]


@pytest.fixture
def lived_in(conn, learner, api, learner_headers):
    """The dev learner with a little of everything, plus one event in the activity log."""
    lid, pid = learner["id"], learner["pseudonym_id"]
    conn.execute("insert into consent_record(learner_id, kind, version, given_at) values (%s, 'service', '2026-10', now())", (lid,))
    conn.execute("insert into mastery(learner_id, competency_code) values (%s, 'FND')", (lid,))
    conn.execute("insert into item_response(learner_id, question_id, question_version, context, correct) "
                 "values (%s, 'q-dt-01', 1, 'unit', false)", (lid,))
    conn.execute("insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at) "
                 "values (%s, 'q-dt-01', 'unit', 'Hỏi', 'Đáp', 'Nguồn', '{}', now())", (lid,))
    session_id = conn.execute("insert into chat_session(learner_pid) values (%s) returning id", (pid,)).fetchone()["id"]
    conn.execute("insert into chat_message(session_id, role, text) values (%s, 'user', 'Câu hỏi riêng của tôi')", (session_id,))
    conn.execute("insert into error_report(target_type, target_id, reason, learner_pid) values ('question', 'q-dt-01', 'other', %s)", (pid,))
    conn.execute("insert into idempotency_key(key, subject, route, status_code, response) values ('k', %s, 'POST /x', 200, '{}')", (pid,))
    conn.execute("insert into activity_event(learner_pid, kind, occurred_at) values (%s, 'visit', now())", (pid,))
    conn.commit()
    return learner


def test_erasing_removes_everything_but_the_pseudonymous_activity_log(api, conn, lived_in, learner_headers):
    r = api.request("DELETE", "/v1/me", headers=learner_headers)
    assert r.status_code == 200 and r.json()["requested_at"]
    assert {t: count(conn, t) for t in TABLES} == {t: 0 for t in TABLES}
    assert count(conn, "activity_event") == 1
    request = conn.execute("select learner_pid, completed_at from deletion_request").fetchone()
    assert request["learner_pid"] == "HV-DEMO-001" and request["completed_at"] is not None


def test_the_token_stops_working_at_once(api, lived_in, learner_headers):
    api.request("DELETE", "/v1/me", headers=learner_headers)
    r = api.get("/v1/me", headers=learner_headers)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_the_code_can_start_a_new_empty_account(api, conn, lived_in, learner_headers):
    api.request("DELETE", "/v1/me", headers=learner_headers)
    pair = api.post("/v1/auth/activate", json={"code": "DEMO-0001"}).json()
    me = api.get("/v1/me", headers={"Authorization": f"Bearer {pair['access_token']}"}).json()
    assert me["pseudonym_id"] != "HV-DEMO-001" and count(conn, "item_response") == 0


def test_another_learner_is_untouched(api, conn, lived_in, learner_headers):
    other = conn.execute(
        "insert into learner(pseudonym_id, exam_date) values ('HV-OTHER', '2027-03-01') returning id").fetchone()["id"]
    conn.execute("insert into learner_identity values (%s, 'Người khác', null)", (other,))
    conn.execute("insert into chat_session(learner_pid) values ('HV-OTHER')")
    conn.commit()
    api.request("DELETE", "/v1/me", headers=learner_headers)
    assert count(conn, "learner") == 1 and count(conn, "learner_identity") == 1 and count(conn, "chat_session") == 1


def test_keep_pseudonymous_removes_the_identity_only(api, conn, lived_in, learner_headers, monkeypatch):
    monkeypatch.setitem(settings()["account_deletion"], "learning_records", "keep_pseudonymous")
    assert api.request("DELETE", "/v1/me", headers=learner_headers).status_code == 200
    assert count(conn, "learner_identity") == 0 and count(conn, "auth_token") == 0
    assert count(conn, "item_response") == 1 and count(conn, "chat_message") == 1
    assert conn.execute("select active from learner").fetchone()["active"] is False
    assert api.get("/v1/me", headers=learner_headers).status_code == 401
    assert api.post("/v1/auth/activate", json={"code": "DEMO-0001"}).status_code == 401   # the account is closed


def test_an_unknown_deletion_mode_is_refused_and_nothing_is_deleted(api, conn, lived_in, learner_headers, monkeypatch):
    monkeypatch.setitem(settings()["account_deletion"], "learning_records", "archive")
    with pytest.raises(RuntimeError, match="account_deletion.learning_records"):   # a 500 outside the test client
        api.request("DELETE", "/v1/me", headers=learner_headers)
    assert count(conn, "learner") == 1 and count(conn, "item_response") == 1 and count(conn, "deletion_request") == 0


def test_staff_cannot_call_it(api, staff_headers):
    assert api.request("DELETE", "/v1/me", headers=staff_headers("admin")).status_code == 403
