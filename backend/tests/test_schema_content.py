"""Content, question bank and review tables. The approval rule lives in the database."""
import psycopg
import pytest
from psycopg.types.json import Jsonb

OPTIONS = Jsonb([{"key": "a", "text": "Đúng", "is_correct": True, "rationale": "Vì đúng."},
                 {"key": "b", "text": "Sai", "is_correct": False, "rationale": "Vì sai."}])
QUESTION = """insert into question(id, version, stem, options, explanation, competency_code, bloom_level,
              difficulty_label, difficulty_b, source_passage_ids, status)
              values (%s, %s, 'Câu hỏi?', %s, 'Giải thích.', 'FND', 2, 'de', -1, '{}', %s)"""


@pytest.fixture
def framework(conn):
    """A topic and two reviewers; returns the reviewers' ids."""
    conn.execute("insert into competency_node(code, level, name) values ('FND', 1, 'Nền tảng')")
    return [conn.execute(
        "insert into staff_user(email, password_hash, display_name, role) values (%s, '!', %s, 'reviewer') returning id",
        (f"r{n}@example.invalid", f"Người thẩm định {n}")).fetchone()["id"] for n in (1, 2)]


def decide(conn, reviewer_id, round_, decision="pass", version=1, comment=None):
    conn.execute("insert into review_decision(target_type, target_id, version, round, reviewer_id, decision, comment) "
                 "values ('question', 'q1', %s, %s, %s, %s, %s)", (version, round_, reviewer_id, decision, comment))


def approve(conn, version=1):
    """Move the question to the end of review, then try to approve it."""
    conn.execute("update question set status = 'in_review_r2' where id = 'q1' and version = %s", (version,))
    conn.execute("update question set status = 'approved' where id = 'q1' and version = %s", (version,))


def approved_question(conn, framework):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    decide(conn, framework[0], 1)
    decide(conn, framework[1], 2)
    approve(conn)


def test_a_question_cannot_be_inserted_as_approved(conn, framework):
    with pytest.raises(psycopg.errors.RaiseException, match="approved needs a pass"):
        conn.execute(QUESTION, ("q1", 1, OPTIONS, "approved"))


def test_two_passes_from_different_reviewers_allow_approval(conn, framework):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    decide(conn, framework[0], 1)
    decide(conn, framework[1], 2)
    approve(conn)
    assert conn.execute("select status from question").fetchone()["status"] == "approved"


@pytest.mark.parametrize("decisions", [
    [],                                   # nobody reviewed
    [(0, 1)],                             # round 1 only
    [(0, 1), (0, 2)],                     # the same reviewer twice
    [(0, 1), (1, 1)],                     # round 2 missing
])
def test_anything_less_does_not(conn, framework, decisions):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    for reviewer, round_ in decisions:
        decide(conn, framework[reviewer], round_)
    with pytest.raises(psycopg.errors.RaiseException, match="approved needs a pass"):
        approve(conn)


def test_a_rejection_in_round_two_does_not_count(conn, framework):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    decide(conn, framework[0], 1)
    decide(conn, framework[1], 2, decision="reject", comment="Sai đáp án.")
    with pytest.raises(psycopg.errors.RaiseException):
        approve(conn)


def test_decisions_on_one_version_do_not_approve_another(conn, framework):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    conn.execute(QUESTION, ("q1", 2, OPTIONS, "draft"))
    decide(conn, framework[0], 1)
    decide(conn, framework[1], 2)
    with pytest.raises(psycopg.errors.RaiseException):
        approve(conn, version=2)


def test_an_approved_question_can_still_be_updated(conn, framework):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    decide(conn, framework[0], 1)
    decide(conn, framework[1], 2)
    approve(conn)
    conn.execute("update question set n_responses = n_responses + 1 where id = 'q1'")
    conn.execute("update question set status = 'retired' where id = 'q1'")


def test_approval_is_reached_only_from_the_second_review_round(conn, framework):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    decide(conn, framework[0], 1)
    decide(conn, framework[1], 2)
    with pytest.raises(psycopg.errors.RaiseException, match="approved needs a pass"):
        conn.execute("update question set status = 'approved' where id = 'q1'")      # straight from draft


def test_a_retired_question_cannot_be_approved_again_on_its_old_reviews(conn, framework):
    approved_question(conn, framework)
    conn.execute("update question set status = 'retired' where id = 'q1'")
    with pytest.raises(psycopg.errors.RaiseException, match="approved needs a pass"):
        conn.execute("update question set status = 'approved' where id = 'q1'")


def test_the_latest_decision_of_a_round_is_the_one_that_counts(conn, framework):
    conn.execute(QUESTION, ("q1", 1, OPTIONS, "draft"))
    decide(conn, framework[0], 1)
    decide(conn, framework[1], 2)
    decide(conn, framework[1], 2, decision="reject", comment="Xem lại: sai đáp án.")
    with pytest.raises(psycopg.errors.RaiseException, match="approved needs a pass"):
        approve(conn)


@pytest.mark.parametrize("change", [
    "stem = 'Câu hỏi khác?'",
    "explanation = 'Giải thích khác.'",
    "id = 'q2'",
    "version = 2",
    "bloom_level = 3",
])
def test_an_approved_question_cannot_be_edited_or_renamed(conn, framework, change):
    approved_question(conn, framework)
    with pytest.raises(psycopg.errors.RaiseException, match="create a new version"):
        conn.execute(f"update question set {change} where id = 'q1'")


def test_a_question_leaving_approved_cannot_change_identity_on_the_way(conn, framework):
    approved_question(conn, framework)
    with pytest.raises(psycopg.errors.RaiseException, match="create a new version"):
        conn.execute("update question set status = 'retired', id = 'q9' where id = 'q1'")


def test_only_one_version_of_a_question_is_approved_at_a_time(conn, framework):
    approved_question(conn, framework)
    conn.execute(QUESTION, ("q1", 2, OPTIONS, "draft"))
    decide(conn, framework[0], 1, version=2)
    decide(conn, framework[1], 2, version=2)
    with pytest.raises(psycopg.errors.UniqueViolation):
        approve(conn, version=2)


def test_review_decisions_cannot_be_changed_or_removed(conn, framework):
    decide(conn, framework[0], 1)
    for sql in ("delete from review_decision", "update review_decision set target_id = 'q2'"):
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute(sql)
        conn.rollback()


def test_content_items_carry_their_topic(conn, framework):
    conn.execute("insert into content_item(id, body, status, competency_code) values ('c1', 'Nội dung', 'draft', 'FND')")
    assert conn.execute("select competency_code from content_item").fetchone()["competency_code"] == "FND"


def test_content_items_follow_the_same_rule(conn, framework):
    with pytest.raises(psycopg.errors.RaiseException, match="approved needs a pass"):
        conn.execute("insert into content_item(id, body, status) values ('c1', 'Nội dung', 'approved')")


def test_a_decision_other_than_pass_needs_a_comment(conn, framework):
    with pytest.raises(psycopg.errors.CheckViolation):
        decide(conn, framework[0], 1, decision="revise", comment="  ")


def test_status_history_is_append_only(conn, framework):
    conn.execute("insert into status_transition(target_type, target_id, version, to_status, actor_label) "
                 "values ('question', 'q1', 1, 'draft', 'Nạp dữ liệu')")
    for sql in ("update status_transition set to_status = 'approved'", "delete from status_transition",
                "delete from status_transition where false"):
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute(sql)
        conn.rollback()


def test_passage_search_vector_is_generated(conn):
    conn.execute("insert into document(id, title, demo_label) values ('d', 'D', 'x')")
    conn.execute("insert into passage(id, document_id, text, text_unaccented, corpus_version) "
                 "values ('p', 'd', 'viêm gan', 'viem gan', 'v')")
    row = conn.execute("select tsv::text as t from passage where id = 'p'").fetchone()
    assert "'viem'" in row["t"] and "'viêm'" in row["t"]


def test_a_form_kind_outside_the_list_is_refused(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into exam_form(id, title, kind, question_ids, seconds_per_question, status) "
                     "values ('f', 'Đề', 'final', '{}', 60, 'approved')")
