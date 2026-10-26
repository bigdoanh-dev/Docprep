"""Chat, suggestions and plumbing tables, and the shape of the whole schema."""
import psycopg
import pytest

EXPECTED_TABLES = {
    "core_issue_group", "core_issue", "exam_competency", "exam_competency_component", "competency_node",
    "organisation", "staff_user", "learner", "learner_identity", "import_batch", "activation_code", "auth_token",
    "consent_record", "deletion_request",
    "document", "passage", "glossary_term", "module", "content_item", "question", "unit", "unit_item", "exam_form",
    "review_decision", "status_transition", "error_report",
    "mastery", "unit_session", "exam_attempt", "attempt_answer", "practice_set", "item_response", "card",
    "card_review", "daily_session", "session_addition", "activity_event",
    "chat_session", "chat_message", "suggestion", "idempotency_key", "audit_log",
    "auth_failure",
}


def test_the_schema_is_exactly_the_data_model(conn):
    names = {r["table_name"] for r in conn.execute(
        "select table_name from information_schema.tables where table_schema = 'public'")}
    assert names - {"alembic_version"} == EXPECTED_TABLES


def test_a_chat_state_outside_the_contract_is_refused(conn):
    session_id = conn.execute("insert into chat_session(learner_pid) values ('HV-1') returning id").fetchone()["id"]
    conn.execute("insert into chat_message(session_id, role, text, state, format) "
                 "values (%s, 'assistant', 'Hỏi lại', 'needs_clarification', 'text')", (session_id,))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into chat_message(session_id, role, text, state) values (%s, 'assistant', 'x', 'plan_proposal')",
                     (session_id,))


def test_a_message_stores_what_the_history_endpoint_returns(conn):
    """ChatMessage in the contract has clarify_options, searched and nearest_chapter; none can be recomputed."""
    session_id = conn.execute("insert into chat_session(learner_pid) values ('HV-1') returning id").fetchone()["id"]
    row = conn.execute(
        """insert into chat_message(session_id, role, text, state, clarify_options, searched, nearest_chapter)
           values (%s, 'assistant', 'x', 'insufficient_evidence', '[]', '[{"document": "D", "range": "Chương 2"}]',
                   '{"passage_id": "p", "label_vi": "D · Chương 2"}') returning *""", (session_id,)).fetchone()
    assert row["searched"][0]["document"] == "D" and row["nearest_chapter"]["passage_id"] == "p"


def test_an_activation_code_can_hold_the_name_until_activation(conn):
    conn.execute("insert into activation_code(code_hash, audience, display_name) values ('h', 'student', 'Nguyễn Thu Hà')")
    assert conn.execute("select display_name from activation_code").fetchone()["display_name"] == "Nguyễn Thu Hà"


def test_the_same_idempotency_key_cannot_be_stored_twice(conn):
    sql = "insert into idempotency_key(key, subject, route, status_code, response) values ('k', 'HV-1', 'POST /x', 200, '{}')"
    conn.execute(sql)
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(sql)


def test_the_audit_log_is_append_only(conn):
    conn.execute("insert into audit_log(actor_type, action) values ('system', 'seed')")
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        conn.execute("delete from audit_log")


def test_removing_a_suggestion_keeps_the_session_addition(conn):
    conn.execute("insert into competency_node(code, level, name) values ('FND', 1, 'Nền tảng')")
    learner_id = conn.execute(
        "insert into learner(pseudonym_id, exam_date) values ('HV-1', '2027-03-01') returning id").fetchone()["id"]
    session_id = conn.execute("insert into chat_session(learner_pid) values ('HV-1') returning id").fetchone()["id"]
    message_id = conn.execute(
        "insert into chat_message(session_id, role, text) values (%s, 'assistant', 'x') returning id",
        (session_id,)).fetchone()["id"]
    suggestion_id = conn.execute(
        "insert into suggestion(learner_id, message_id, kind, competency_code, reason_vi) "
        "values (%s, %s, 'add_to_tomorrow', 'FND', 'Lý do') returning id", (learner_id, message_id)).fetchone()["id"]
    conn.execute("insert into session_addition(learner_id, for_date, competency_code, suggestion_id) "
                 "values (%s, '2026-10-11', 'FND', %s)", (learner_id, suggestion_id))
    conn.execute("delete from chat_session where id = %s", (session_id,))
    assert conn.execute("select suggestion_id from session_addition").fetchone()["suggestion_id"] is None
