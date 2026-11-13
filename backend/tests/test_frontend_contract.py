"""Real API regressions for the merged learner frontend's data contract."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import threading

import pytest
from psycopg.types.json import Jsonb

from app.errors import ApiError
from app.repo import cards as cards_repo
from app.services import cards as cards_service
from tests.conftest import _issue, _test_conn, answer_all
from tests.test_daily_session import add_due_cards


def limits(client, new=1, reviews=1):
    response = client.patch("/v1/me", json={"new_cards_per_day": new, "max_reviews_per_day": reviews})
    assert response.status_code == 200, response.text


def queue(client):
    response = client.get("/v1/cards/due", params={"limit": 200})
    assert response.status_code == 200, response.text
    return response.json()


def new_question_version(conn, original, **changes):
    conn.execute("update question set status = 'retired' where id = %s and version = %s",
                 (original["id"], original["version"]))
    edited = {**original, **changes, "version": original["version"] + 1, "status": "in_review_r2", "n_responses": 0}
    conn.execute("insert into question select (jsonb_populate_record(null::question, %s)).*", (Jsonb(edited),))
    reviewers = conn.execute("select id from staff_user where is_demo order by id limit 2").fetchall()
    for round_, reviewer in enumerate(reviewers, start=1):
        conn.execute("insert into review_decision(target_type, target_id, version, round, reviewer_id, decision) "
                     "values ('question', %s, %s, %s, %s, 'pass')",
                     (original["id"], edited["version"], round_, reviewer["id"]))
    conn.execute("update question set status = 'approved' where id = %s and version = %s",
                 (original["id"], edited["version"]))
    conn.commit()


def test_empty_assessments_include_all_groups_and_issues(learner_api):
    data = learner_api.get("/v1/progress/skills").json()
    assert len(data["specialties"]) == len(data["bloom_by_specialty"]) == 8
    assert sum(len(g["issues"]) for g in data["issues_by_specialty"]) == 54
    assert all(i["total"] == i["correct"] == 0 for g in data["issues_by_specialty"] for i in g["issues"])
    assert [l["label_vi"] for l in data["levels"]] == ["Ghi nhớ", "Hiểu", "Vận dụng", "Phân tích", "Đánh giá", "Sáng tạo"]


def test_results_and_progress_count_answered_items_and_preserve_unknowns(learner_api, api, tokens_for_new_learner):
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    answer_all(learner_api, attempt, wrong=2, blank=3)
    result = learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit").json()
    assert (result["total"], result["score"], result["blank"]) == (10, 5, 3)
    progress = learner_api.get("/v1/progress/skills").json()
    for data in (result, progress):
        legacy = data.get("unclassified_bloom", {"correct": 0, "total": 0})
        assert sum(l["total"] for l in data["levels"]) + legacy["total"] == 7
        assert sum(l["correct"] for l in data["levels"]) + legacy["correct"] == 5
        assert sum(s["total"] for s in data["specialties"]) == 7
        assert sum(l["total"] for g in data["bloom_by_specialty"] for l in g["levels"]) + legacy["total"] == 7
        assert all(s["total"] == 0 for s in data["specialties"][1:])
        # Foundation answers belong to g1, but are never assigned a made-up core issue.
        assert sum(i["total"] for g in data["issues_by_specialty"] for i in g["issues"]) < 7
    for key in ("specialties", "issues_by_specialty"):
        assert result[key] == progress[key]
    other = tokens_for_new_learner()
    assert api.get(f"/v1/attempts/{attempt['attempt_id']}/results", headers=other).status_code == 404
    assert all(s["total"] == 0 for s in api.get("/v1/progress/skills", headers=other).json()["specialties"])


def test_question_review_and_summary_use_the_served_version(learner_api, conn):
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    qid = "q-tc-03"
    original = conn.execute("select * from question where id = %s and status = 'approved'", (qid,)).fetchone()
    new_question_version(conn, original, competency_code="CI-06", core_issue_id=6,
                         bloom_level=3 if original["bloom_level"] != 3 else 1, difficulty_label="kho")
    chosen = next(o["key"] for o in original["options"] if o["is_correct"])
    learner_api.put(f"/v1/attempts/{attempt['attempt_id']}/answers/{qid}", json={"chosen": chosen})
    result = learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit").json()
    review = learner_api.get(f"/v1/attempts/{attempt['attempt_id']}/items/{qid}").json()
    assert review["module_id"] == "g1" and review["core_issue_id"] == original["core_issue_id"]
    assert review["bloom_level"] == original["bloom_level"]
    assert review["bloom_label"] == result["levels"][original["bloom_level"] - 1]["label_vi"]
    assert result["specialties"][0]["total"] == 1 and result["specialties"][1]["total"] == 0
    assert result["levels"][original["bloom_level"] - 1]["total"] == 1


def test_exam_scope_distinguishes_single_module_and_assembly(learner_api, conn):
    forms = {f["id"]: f for f in learner_api.get("/v1/exams").json()["items"]}
    assert forms["de-thi-thu-1"]["module_id"] == "g1"
    assert forms["de-thi-thu-1"]["module_name"]
    assert forms["de-tu-rap"]["module_id"] is None
    original = conn.execute("select * from question where id = 'q-tc-03' and status = 'approved'").fetchone()
    new_question_version(conn, original, competency_code="CI-06", core_issue_id=6)
    forms = {f["id"]: f for f in learner_api.get("/v1/exams").json()["items"]}
    assert forms["de-thi-thu-1"]["module_id"] is None  # now genuinely spans two modules


def test_practice_items_include_real_classification(learner_api, conn, learner):
    conn.execute("insert into session_addition(learner_id, for_date, competency_code) values (%s, '2026-10-10', 'CI-04')",
                 (learner["id"],))
    conn.commit()
    practice = learner_api.get("/v1/session/today/practice").json()
    assert practice["items"]
    for item in practice["items"]:
        assert item["module_id"] == "g1" and item["module_name"]
        assert item["core_issue_id"] == 4 and item["core_issue_name"]
        assert item["difficulty_label"] and item["bloom_label"]


def test_all_due_displays_share_daily_limits_and_idempotent_reviews(learner_api, conn, learner):
    add_due_cards(conn, learner, 3)
    limits(learner_api)
    first = queue(learner_api)
    assert len(first["items"]) == first["total_due"] == 1
    assert learner_api.get("/v1/home").json()["due_cards"] == 1
    assert sum(d["due"] for d in learner_api.get("/v1/decks").json()["items"]) == 1
    rhythm = learner_api.get("/v1/progress/rhythm").json()
    assert rhythm["memory"]["due_today"] == rhythm["due_forecast"][0]["count"] == 1
    session = learner_api.get("/v1/session/today").json()
    assert next(s for s in session["steps"] if s["kind"] == "cards")["count"] == 1
    cid = first["items"][0]["id"]
    key = {"Idempotency-Key": "daily-limit-retry"}
    rated = learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 1}, headers=key)
    assert rated.status_code == 200 and rated.json()["remaining_due"] == 0
    assert learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 1}, headers=key).json() == rated.json()
    assert queue(learner_api) == {"items": [], "total_due": 0}
    another = conn.execute("select id from card where id != %s order by id limit 1", (cid,)).fetchone()["id"]
    rejected = learner_api.post(f"/v1/cards/{another}/reviews", json={"rating": 3})
    assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "review_limit_reached"
    assert conn.execute("select count(*) n from card_review").fetchone()["n"] == 1


def test_new_card_cap_still_allows_due_learning_cards(learner_api, conn, learner, clock):
    add_due_cards(conn, learner, 3)
    limits(learner_api, new=1, reviews=5)
    cid = queue(learner_api)["items"][0]["id"]
    assert learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 1}).status_code == 200
    another = conn.execute("select id from card where id != %s order by id limit 1", (cid,)).fetchone()["id"]
    response = learner_api.post(f"/v1/cards/{another}/reviews", json={"rating": 3})
    assert response.status_code == 409 and response.json()["error"]["code"] == "new_card_limit_reached"
    clock.advance(minutes=15)
    assert [c["id"] for c in queue(learner_api)["items"]] == [cid]
    assert learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 1}).status_code == 200
    assert cards_repo.budget(conn, learner["id"], clock()) == {"reviews": 3, "new": 0}


def test_limits_reset_at_local_midnight_and_not_by_suspension(learner_api, conn, learner, clock):
    clock.now = clock.now.replace(hour=16, minute=59)  # 23:59 in Vietnam
    learner_api.headers.update(_issue("learner", learner["id"], clock()))
    add_due_cards(conn, learner, 3)
    limits(learner_api)
    cid = queue(learner_api)["items"][0]["id"]
    assert learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 3}).status_code == 200
    assert learner_api.patch(f"/v1/cards/{cid}", json={"suspended": True}).status_code == 200
    assert queue(learner_api)["total_due"] == 0
    clock.advance(minutes=2)
    assert queue(learner_api)["total_due"] == 1


def test_two_cards_cannot_spend_the_last_slot_concurrently(conn, learner, clock):
    add_due_cards(conn, learner, 2)
    conn.execute("update learner set max_reviews_per_day = 1 where id = %s", (learner["id"],))
    conn.commit()
    ids = [r["id"] for r in conn.execute("select id from card order by id")]
    conn.commit()
    barrier = threading.Barrier(2)

    def rate(cid):
        barrier.wait(timeout=10)
        try:
            with _test_conn() as c:
                cards_service.review(c, learner, cid, 3, clock())
            return "ok"
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(rate, ids)) == ["ok", "review_limit_reached"]
    assert conn.execute("select count(*) n from card_review").fetchone()["n"] == 1


def test_lowering_limit_during_session_does_not_leave_an_impossible_step(learner_api, conn, learner):
    add_due_cards(conn, learner, 3)
    assert learner_api.get("/v1/session/today").json()["steps"][0]["count"] == 3
    limits(learner_api)
    cid = queue(learner_api)["items"][0]["id"]
    assert learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 3}).status_code == 200
    assert learner_api.get("/v1/session/today").json()["steps"][0]["done"] is True


@pytest.mark.parametrize("limited", ["reviews", "new"])
def test_waiting_request_counts_a_review_with_a_later_request_timestamp(conn, learner, clock, limited):
    """Now is captured before the learner lock: arrival order need not be commit order."""
    add_due_cards(conn, learner, 2)
    conn.execute("update learner set max_reviews_per_day = %s, new_cards_per_day = 1 where id = %s",
                 (1 if limited == "reviews" else 5, learner["id"]))
    conn.commit()
    ids = [r["id"] for r in conn.execute("select id from card order by id")]
    conn.commit()
    with _test_conn() as c:
        cards_service.review(c, learner, ids[0], 3, clock() + timedelta(milliseconds=1))
    # This request arrived earlier but acquired the lock after the first committed.
    with pytest.raises(ApiError) as error:
        with _test_conn() as c:
            cards_service.review(c, learner, ids[1], 3, clock())
    assert error.value.code == ("review_limit_reached" if limited == "reviews" else "new_card_limit_reached")
    assert conn.execute("select count(*) n from card_review").fetchone()["n"] == 1


def test_due_pagination_preserves_total_and_budget(learner_api, conn, learner):
    add_due_cards(conn, learner, 5)
    limits(learner_api, new=4, reviews=4)
    full = queue(learner_api)
    first = learner_api.get("/v1/cards/due", params={"limit": 2, "offset": 0}).json()
    second = learner_api.get("/v1/cards/due", params={"limit": 2, "offset": 2}).json()
    assert first["items"] + second["items"] == full["items"]
    assert first["total_due"] == second["total_due"] == 4
    assert learner_api.get("/v1/cards/due", params={"offset": 4}).json() == {"items": [], "total_due": 4}
    assert learner_api.get("/v1/cards/due", params={"limit": 201}).status_code == 422
    assert learner_api.get("/v1/cards/due", params={"offset": -1}).status_code == 422
