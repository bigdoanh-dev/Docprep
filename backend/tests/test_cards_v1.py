"""Thẻ ôn under /v1: the due queue and reviews. Ported from the kickoff demo's test_cards_api.py."""
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app.engine.scheduler import new_state
from tests.conftest import _issue, answer_all, make_wrong_unit_answer

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)


def due(client, **params) -> list[dict]:
    return client.get("/v1/cards/due", params=params).json()["items"]


def test_no_cards_at_start(learner_api):
    assert learner_api.get("/v1/cards/due").json() == {"items": [], "total_due": 0}


def test_due_card_listed_with_origin_and_preview(learner_api):
    make_wrong_unit_answer(learner_api)
    cards = due(learner_api)
    assert len(cards) == 1
    c = cards[0]
    assert c["origin"] == "Từ quiz học phần" and c["module"] == "Sức khỏe quần thể và dự phòng"
    assert c["front"].startswith("Một xã có 2.000 dân") and "2,5%" in c["back"]
    assert c["citation"] == "Dịch tễ học cơ bản, tr. 58" and c["source_passage_id"] == "dt-p01"
    assert set(c["preview"]) == {"1", "2", "3", "4"}
    assert c["preview"]["1"] <= c["preview"]["2"] <= c["preview"]["3"] <= c["preview"]["4"]


def test_mock_cards_have_mock_origin(learner_api):
    a = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    answer_all(learner_api, a, wrong=1)
    learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit")
    assert [c["origin"] for c in due(learner_api)] == ["Từ đề thi thử"]


def test_review_moves_card_out_of_due_until_it_is_due_again(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)
    cid = due(learner_api)[0]["id"]
    r = learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 3}).json()
    assert r["card_id"] == cid and r["remaining_due"] == 0 and due(learner_api) == []
    row = conn.execute("select reps, lapses, due_at from card").fetchone()
    assert (row["reps"], row["lapses"]) == (1, 0) and row["due_at"] > clock()
    assert datetime.fromisoformat(r["due_at"]) == row["due_at"]
    review = conn.execute("select rating, scheduled_seconds from card_review").fetchone()
    assert review["rating"] == 3 and review["scheduled_seconds"] == int((row["due_at"] - clock()).total_seconds()) > 0
    clock.advance(seconds=review["scheduled_seconds"] + 1)
    learner_api.headers.update(_issue("learner", learner["id"], clock()))    # the access token may have expired
    assert [c["id"] for c in due(learner_api)] == [cid]


def test_again_counts_a_lapse(learner_api, conn):
    make_wrong_unit_answer(learner_api)
    cid = due(learner_api)[0]["id"]
    learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 1})
    assert conn.execute("select lapses from card").fetchone()["lapses"] == 1


def test_bad_rating_and_unknown_card_rejected(learner_api):
    make_wrong_unit_answer(learner_api)
    cid = due(learner_api)[0]["id"]
    assert learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 5}).status_code == 422
    assert learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 0}).status_code == 422
    r = learner_api.post("/v1/cards/999/reviews", json={"rating": 3})
    assert r.status_code == 404 and r.json()["error"]["code"] == "card_not_found"


def test_validation_errors_use_the_api_error_shape(learner_api):
    make_wrong_unit_answer(learner_api)
    cid = due(learner_api)[0]["id"]
    r = learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": "abc"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request" and r.json()["error"]["message_vi"]


# ---- added with the port ----------------------------------------------------------------------

def test_a_review_retried_with_the_same_key_is_applied_once(learner_api, conn):
    make_wrong_unit_answer(learner_api)
    card = due(learner_api)[0]
    key = {"Idempotency-Key": "review-1"}
    first = learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3, "time_ms": 9_000}, headers=key).json()
    assert learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3, "time_ms": 9_000}, headers=key).json() == first
    assert conn.execute("select reps from card").fetchone()["reps"] == 1
    assert conn.execute("select count(*) c from card_review").fetchone()["c"] == 1


def test_without_a_key_a_second_review_counts(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)
    card = due(learner_api)[0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 1})
    clock.advance(hours=1)
    learner_api.headers.update(_issue("learner", learner["id"], clock()))
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 1})
    assert conn.execute("select reps, lapses from card").fetchone() == {"reps": 2, "lapses": 2}


def test_another_learners_card_is_not_found_and_not_listed(api, learner_api, tokens_for_new_learner, conn):
    make_wrong_unit_answer(learner_api)
    card = due(learner_api)[0]
    other = tokens_for_new_learner()
    assert api.get("/v1/cards/due", headers=other).json() == {"items": [], "total_due": 0}
    r = api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3}, headers=other)
    assert r.status_code == 404 and r.json()["error"]["code"] == "card_not_found"
    assert conn.execute("select reps from card").fetchone()["reps"] == 0


def test_the_page_is_limited_but_the_total_is_not(learner_api, conn, learner):
    for n in range(3):
        conn.execute("insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at) "
                     "select %s, id, 'unit', stem, 'Đáp án', 'Nguồn', %s, %s from question "
                     "order by id offset %s limit 1", (learner["id"], Jsonb(new_state(NOW)), NOW - timedelta(days=1), n))
    conn.commit()
    body = learner_api.get("/v1/cards/due", params={"limit": 2}).json()
    assert len(body["items"]) == 2 and body["total_due"] == 3


def test_a_suspended_card_is_not_due(learner_api, conn):
    make_wrong_unit_answer(learner_api)
    conn.execute("update card set suspended = true")
    conn.commit()
    assert learner_api.get("/v1/cards/due").json() == {"items": [], "total_due": 0}


def test_a_review_is_logged_with_its_duration(learner_api, conn):
    make_wrong_unit_answer(learner_api)
    card = due(learner_api)[0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3, "time_ms": 9_000})
    assert conn.execute("select duration_ms from activity_event where kind = 'card_review'").fetchone()["duration_ms"] == 9_000
    assert conn.execute("select time_ms from card_review").fetchone()["time_ms"] == 9_000


def test_a_card_of_a_question_retired_since_is_still_shown(learner_api, conn):
    make_wrong_unit_answer(learner_api)
    conn.execute("update question set status = 'retired' where id = 'q-dt-01'")
    conn.commit()
    assert [c["source_passage_id"] for c in due(learner_api)] == ["dt-p01"]


def test_mock_mode_still_serves_the_example(mock_client):
    assert mock_client.get("/v1/cards/due").status_code == 200
