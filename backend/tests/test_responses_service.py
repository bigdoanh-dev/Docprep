"""record_response: the single path for a scored answer. Ported from the kickoff demo's test_responses.py."""
from datetime import datetime, timezone

import pytest

from app.errors import ApiError
from app.repo import content
from app.services.responses import ranking, record_response, require_question, topic_names, topic_states
from tests.conftest import correct_key, wrong_key

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)


def q(conn, question_id: str) -> dict:
    return content.approved_question(conn, question_id)


def test_wrong_answer_creates_one_card_and_moves_elo(conn, learner):
    bad = wrong_key(conn, "q-dt-07")
    r1 = record_response(conn, learner, q(conn, "q-dt-07"), bad, "mock", NOW)
    r2 = record_response(conn, learner, q(conn, "q-dt-07"), bad, "mock", NOW)
    assert not r1.correct and r1.card_id is not None and r2.card_id is None
    m = conn.execute("select theta, n_responses from mastery where competency_code='FND'").fetchone()
    assert m["theta"] < 0 and m["n_responses"] == 2
    row = conn.execute("select difficulty_b, n_responses from question where id='q-dt-07'").fetchone()
    assert row["n_responses"] == 2 and row["difficulty_b"] > -1.0
    assert conn.execute("select count(*) c from item_response where card_id is not null").fetchone()["c"] == 1


def test_correct_answer_creates_no_card(conn, learner):
    key = correct_key(conn, "q-dt-07")
    r = record_response(conn, learner, q(conn, "q-dt-07"), key, "mock", NOW)
    assert r.correct and r.card_id is None


def test_card_back_has_answer_explanation_and_citation(conn, learner):
    record_response(conn, learner, q(conn, "q-dt-01"), "b", "unit", NOW)
    c = conn.execute("select front, back, citation, source_context, created_by, due_at from card").fetchone()
    assert c["front"].startswith("Một xã có 2.000 dân") and "2,5%" in c["back"]
    assert c["citation"] == "Dịch tễ học cơ bản, tr. 58"
    assert c["source_context"] == "unit" and c["created_by"] == "rule" and c["due_at"] == NOW


def test_legal_source_cited_by_article(conn, learner):
    record_response(conn, learner, q(conn, "q-tc-04"), wrong_key(conn, "q-tc-04"), "mock", NOW)
    c = conn.execute("select citation from card").fetchone()
    assert c["citation"] == "Luật Phòng, chống bệnh truyền nhiễm 2007, Điều 3, khoản 1, điểm a"


def test_unknown_question_raises_404(conn, learner):
    with pytest.raises(ApiError) as e:
        require_question(conn, "q-nope")
    assert e.value.status == 404 and e.value.code == "question_not_found"
    assert require_question(conn, "q-dt-01")["id"] == "q-dt-01"


def test_topic_unassessed_until_min_responses(conn, learner):
    key = correct_key(conn, "q-dt-07")
    for _ in range(2):
        record_response(conn, learner, q(conn, "q-dt-07"), key, "mock", NOW)
    states = {t.code: t for t in topic_states(conn, learner["id"])}
    assert states["FND"].mastery is None
    record_response(conn, learner, q(conn, "q-dt-07"), key, "mock", NOW)
    states = {t.code: t for t in topic_states(conn, learner["id"])}
    assert states["FND"].mastery > 0.5


def test_ranking_puts_focus_module_topics_first(conn, learner):
    states = topic_states(conn, learner["id"])
    assert len(states) == 55 and all(s.mastery is None for s in states)
    order = ranking(conn, learner)
    g1 = {"CI-01", "CI-02", "CI-03", "CI-04", "CI-05", "FND"}
    assert set(order[:6]) == g1 and order[:5] == ["CI-01", "CI-02", "CI-03", "CI-04", "CI-05"]   # weight 3.6 each, FND 2.0


def test_a_wrong_unit_answer_is_logged_with_its_duration_and_the_card(conn, learner):
    record_response(conn, learner, q(conn, "q-dt-01"), "b", "unit", NOW, time_ms=41_000)
    kinds = [(r["kind"], r["duration_ms"]) for r in conn.execute("select kind, duration_ms from activity_event order by id")]
    assert kinds == [("unit_response", 41_000), ("cards_created", None)]
    assert conn.execute("select learner_pid from activity_event limit 1").fetchone()["learner_pid"] == learner["pseudonym_id"]
    assert conn.execute("select time_ms from item_response").fetchone()["time_ms"] == 41_000


def test_exam_answers_write_no_per_answer_event(conn, learner):
    record_response(conn, learner, q(conn, "q-dt-07"), "a", "mock", NOW, attempt_id=None)
    assert conn.execute("select count(*) c from activity_event where kind <> 'cards_created'").fetchone()["c"] == 0


def test_a_diagnostic_card_says_where_it_came_from(conn, learner):
    record_response(conn, learner, q(conn, "q-dt-01"), wrong_key(conn, "q-dt-01"), "diagnostic", NOW)
    assert conn.execute("select source_context from card").fetchone()["source_context"] == "diagnostic"


def test_a_retired_question_can_still_be_scored(conn, learner):
    conn.execute("update question set status = 'retired' where id = 'q-dt-07'")
    record_response(conn, learner, content.question_as_served(conn, "q-dt-07", 1), "a", "mock", NOW)
    assert conn.execute("select n_responses from question where id = 'q-dt-07'").fetchone()["n_responses"] == 1


def test_topic_names_come_from_the_competency_tree(conn, learner):
    names = topic_names(conn)
    assert names["CI-01"] == "Bệnh truyền nhiễm có nguy cơ gây dịch" and "FND" in names
