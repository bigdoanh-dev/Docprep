"""Learning records and the activity log."""
import psycopg
import pytest


@pytest.fixture
def learner_id(conn):
    conn.execute("insert into competency_node(code, level, name) values ('FND', 1, 'Nền tảng')")
    return conn.execute(
        "insert into learner(pseudonym_id, exam_date) values ('HV-1', '2027-03-01') returning id").fetchone()["id"]


def test_one_daily_session_per_learner_and_day(conn, learner_id):
    sql = "insert into daily_session(learner_id, local_date, steps) values (%s, '2026-10-10', '[]')"
    conn.execute(sql, (learner_id,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(sql, (learner_id,))


def test_one_card_per_learner_and_question(conn, learner_id):
    sql = ("insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at) "
           "values (%s, 'q1', 'unit', 'Hỏi', 'Đáp', 'Nguồn', '{}', now())")
    conn.execute(sql, (learner_id,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(sql, (learner_id,))


@pytest.mark.parametrize("sql", [
    "insert into item_response(learner_id, question_id, question_version, context, correct) values (%s, 'q1', 1, 'exam', true)",
    "insert into practice_set(learner_id, source, competency_code, question_ids) values (%s, 'homework', 'FND', '{}')",
])
def test_contexts_and_sources_outside_the_lists_are_refused(conn, learner_id, sql):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(sql, (learner_id,))


def test_all_four_response_contexts_are_accepted(conn, learner_id):
    for context in ("unit", "practice", "diagnostic", "mock"):
        conn.execute("insert into item_response(learner_id, question_id, question_version, context, correct) "
                     "values (%s, 'q1', 1, %s, true)", (learner_id, context))


def test_activity_is_append_only_and_typed(conn, learner_id):
    conn.execute("insert into activity_event(learner_pid, kind, occurred_at) values ('HV-1', 'visit', now())")
    with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        conn.execute("update activity_event set kind = 'chat_turn'")
    conn.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into activity_event(learner_pid, kind, occurred_at) values ('HV-1', 'login', now())")


def test_erasing_a_learner_removes_their_learning_records(conn, learner_id):
    conn.execute("insert into mastery(learner_id, competency_code) values (%s, 'FND')", (learner_id,))
    conn.execute("insert into item_response(learner_id, question_id, question_version, context, correct) "
                 "values (%s, 'q1', 1, 'unit', false)", (learner_id,))
    card_id = conn.execute(
        "insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at) "
        "values (%s, 'q1', 'unit', 'Hỏi', 'Đáp', 'Nguồn', '{}', now()) returning id", (learner_id,)).fetchone()["id"]
    conn.execute("insert into card_review(card_id, rating, reviewed_at, scheduled_seconds) values (%s, 3, now(), 600)",
                 (card_id,))
    conn.execute("delete from learner where id = %s", (learner_id,))
    for table in ("mastery", "item_response", "card", "card_review"):
        assert conn.execute(f"select count(*) c from {table}").fetchone()["c"] == 0, table
