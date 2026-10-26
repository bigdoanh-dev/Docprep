"""Practice sets: a few approved questions on one competency, graded like any other answer, with a
worked example after a wrong one and a summary of what the set changed."""
import json
import threading
from datetime import datetime, timezone

from app.schemas.practice import PracticeFeedback, PracticeSetView
from app.services import practice
from tests.conftest import _test_conn, correct_key, make_wrong_unit_answer, wrong_key

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)      # the test clock's start


def make_set(conn, learner, code: str = "FND", wrong: int = 1) -> dict:
    built = practice.build(conn, learner, "session", code, wrong, False, NOW)
    conn.commit()
    return built


def test_a_set_holds_six_approved_questions_with_their_reasons(learner_api, conn, learner):
    make_wrong_unit_answer(learner_api)                                   # q-dt-01, seen today
    s = make_set(conn, learner)
    view = learner_api.get(f"/v1/practice-sets/{s['id']}").json()
    PracticeSetView.model_validate(view)
    assert (view["source"], view["competency_code"], view["total"], view["answered"], view["completed"]) == (
        "session", "FND", 6, 0, False)
    assert view["topic"] == "Khái niệm cơ bản của y học dự phòng"
    assert [i["question_id"] for i in view["items"]] == ["q-dt-02", "q-dt-03", "q-dt-04", "q-dt-05", "q-dt-06", "q-dt-07"]
    assert [i["n"] for i in view["items"]] == [1, 2, 3, 4, 5, 6]
    assert view["items"][0]["reason_vi"] == ("Bạn sai 1 câu về Khái niệm cơ bản của y học dự phòng trong 7 ngày qua"
                                             " · bạn chưa gặp câu này trong 14 ngày.")
    assert "is_correct" not in json.dumps(view) and "rationale" not in json.dumps(view)
    assert all(i["feedback"] is None and i["chosen"] is None for i in view["items"])
    assert conn.execute("select count(*) c from activity_event where kind = 'practice_set_built'").fetchone()["c"] == 1
    assert conn.execute("select question_versions from practice_set").fetchone()["question_versions"]["q-dt-02"] == 1


def test_the_options_of_a_set_are_shuffled_once_and_stay_put(learner_api, conn, learner):
    s = make_set(conn, learner)
    first = learner_api.get(f"/v1/practice-sets/{s['id']}").json()["items"]
    again = learner_api.get(f"/v1/practice-sets/{s['id']}").json()["items"]
    shown = {i["question_id"]: [o["key"] for o in i["options"]] for i in first}
    assert shown == {i["question_id"]: [o["key"] for o in i["options"]] for i in again}      # a reload shows the same order
    authored = {qid: [o["key"] for o in conn.execute("select options from question where id = %s", (qid,)).fetchone()["options"]]
                for qid in shown}
    assert all(sorted(shown[qid]) == sorted(authored[qid]) for qid in shown)                # the same options
    assert shown != authored                                                                # not in the authored order
    texts = {o["key"]: o["text"] for o in first[0]["options"]}
    assert texts["a"] == "2,5%" and texts["b"] == "5%"                                      # a key keeps its text
    f = learner_api.post(f"/v1/practice-sets/{s['id']}/responses", json={"question_id": "q-dt-01", "chosen": "a"}).json()
    assert f["correct"] is True and f["correct_key"] == "a"                                 # graded by key, wherever it is shown


def test_a_wrong_answer_gives_the_explanation_a_card_and_the_example(learner_api, conn, learner):
    s = make_set(conn, learner)                                            # nothing seen: q-dt-01 is the first item
    r = learner_api.post(f"/v1/practice-sets/{s['id']}/responses", json={"question_id": "q-dt-01", "chosen": "b",
                                                                        "time_ms": 52_000})
    f = r.json()
    PracticeFeedback.model_validate(f)
    assert (f["correct"], f["correct_key"], f["card_created"], f["next"]) == (False, "a", True, {"kind": "same_type"})
    assert f["explanation"].startswith("50 ÷ 2.000 = 2,5%") and set(f["rationales"]) == {"a", "b", "c", "d"}
    assert f["citations"][0]["passage_id"] == "dt-p01"
    assert f["remediation"]["title"] == "Ví dụ · Tính từng bước" and f["remediation"]["reason"] == "Được thêm vì bạn chọn 5%"
    assert f["remediation"]["citations"][0]["passage_id"] == "dt-p01" and "2,5%" in f["remediation"]["body"]
    row = conn.execute("select context, practice_set_id, time_ms from item_response").fetchone()
    assert row == {"context": "practice", "practice_set_id": s["id"], "time_ms": 52_000}
    kinds = [e["kind"] for e in conn.execute("select kind from activity_event order by id")]
    assert kinds == ["practice_set_built", "practice_response", "cards_created"]     # the example is shown, nothing is inserted
    answered = learner_api.get(f"/v1/practice-sets/{s['id']}").json()
    assert answered["answered"] == 1 and answered["items"][0]["chosen"] == "b" and answered["items"][0]["feedback"] == f


def test_a_right_answer_brings_no_example_and_no_card(learner_api, conn, learner):
    s = make_set(conn, learner)
    f = learner_api.post(f"/v1/practice-sets/{s['id']}/responses", json={"question_id": "q-dt-01", "chosen": "a"}).json()
    assert f["correct"] is True and f["remediation"] is None and f["card_created"] is False


def test_the_same_answer_sent_twice_is_recorded_once(learner_api, conn, learner):
    s = make_set(conn, learner)
    url, body = f"/v1/practice-sets/{s['id']}/responses", {"question_id": "q-dt-01", "chosen": "b"}
    first = learner_api.post(url, json=body, headers={"Idempotency-Key": "k"}).json()
    assert learner_api.post(url, json=body, headers={"Idempotency-Key": "k"}).json() == first      # the retry
    assert learner_api.post(url, json=body).json() == first                                        # a second tap
    assert learner_api.post(url, json={**body, "chosen": "a"}).json() == first                     # the answer stands
    assert conn.execute("select count(*) c from item_response").fetchone()["c"] == 1
    assert conn.execute("select n_responses from mastery where competency_code = 'FND'").fetchone()["n_responses"] == 1
    assert conn.execute("select count(*) c from card").fetchone()["c"] == 1


def test_two_taps_at_once_are_one_answer(conn, learner):
    s = make_set(conn, learner)
    errors, feedback = [], []

    def tap():
        try:
            with _test_conn() as c:
                feedback.append(practice.answer(c, learner, s["id"], "q-dt-01", "b", NOW))
        except Exception as e:  # noqa: BLE001 — the test reports whatever went wrong
            errors.append(e)

    threads = [threading.Thread(target=tap) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert errors == [] and feedback[0] == feedback[1]
    assert conn.execute("select count(*) c from item_response").fetchone()["c"] == 1


def test_the_last_answer_says_done_and_completion_reports_what_changed(learner_api, conn, learner):
    s = make_set(conn, learner)
    ids = [i["question_id"] for i in learner_api.get(f"/v1/practice-sets/{s['id']}").json()["items"]]
    for n, qid in enumerate(ids):
        chosen = wrong_key(conn, qid) if n < 2 else correct_key(conn, qid)
        f = learner_api.post(f"/v1/practice-sets/{s['id']}/responses", json={"question_id": qid, "chosen": chosen}).json()
        assert f["next"] == {"kind": "done" if n == 5 else "same_type"}
    summary = learner_api.post(f"/v1/practice-sets/{s['id']}/complete").json()
    assert summary["graded"] == {"correct": 4, "total": 6} and summary["mastery_updated"] == {"competencies": 1}
    assert summary["cards_created"] == {"n": 2}
    assert learner_api.post(f"/v1/practice-sets/{s['id']}/complete").json() == summary              # stored, not recomputed
    assert conn.execute("select summary from practice_set").fetchone()["summary"] == summary
    view = learner_api.get(f"/v1/practice-sets/{s['id']}").json()
    assert view["completed"] is True and view["answered"] == 6


def test_a_perfect_set_claims_no_cards(learner_api, conn, learner):
    s = make_set(conn, learner)
    for i in learner_api.get(f"/v1/practice-sets/{s['id']}").json()["items"]:
        learner_api.post(f"/v1/practice-sets/{s['id']}/responses",
                         json={"question_id": i["question_id"], "chosen": correct_key(conn, i["question_id"])})
    summary = learner_api.post(f"/v1/practice-sets/{s['id']}/complete").json()
    assert summary["graded"] == {"correct": 6, "total": 6} and summary["cards_created"] is None
    assert summary["mastery_updated"] == {"competencies": 1}


def test_a_set_closed_without_an_answer_reports_the_grade_alone(learner_api, conn, learner):
    s = make_set(conn, learner)
    summary = learner_api.post(f"/v1/practice-sets/{s['id']}/complete").json()
    assert summary == {"graded": {"correct": 0, "total": 6}, "mastery_updated": None, "cards_created": None, "tomorrow": None}
    r = learner_api.post(f"/v1/practice-sets/{s['id']}/responses", json={"question_id": "q-dt-01", "chosen": "a"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "set_completed"
    assert conn.execute("select count(*) c from item_response").fetchone()["c"] == 0


def test_refusals(learner_api, conn, learner, api, tokens_for_new_learner):
    s = make_set(conn, learner)
    url = f"/v1/practice-sets/{s['id']}"
    r = learner_api.post(f"{url}/responses", json={"question_id": "q-tc-01", "chosen": "a"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "question_not_in_set"
    r = learner_api.post(f"{url}/responses", json={"question_id": "q-dt-01", "chosen": "z"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_option"
    other = tokens_for_new_learner()
    for method, path, body in [("GET", url, None), ("POST", f"{url}/responses", {"question_id": "q-dt-01", "chosen": "a"}),
                               ("POST", f"{url}/complete", None)]:
        r = api.request(method, path, json=body, headers=other)
        assert r.status_code == 404 and r.json()["error"]["code"] == "set_not_found", path
    assert learner_api.get("/v1/practice-sets/999").json()["error"]["code"] == "set_not_found"
    assert conn.execute("select count(*) c from item_response").fetchone()["c"] == 0
    assert conn.execute("select completed_at from practice_set").fetchone()["completed_at"] is None


def test_a_retired_question_is_not_put_into_a_new_set(conn, learner):
    conn.execute("update question set status = 'retired' where id = 'q-dt-01'")
    assert "q-dt-01" not in make_set(conn, learner)["question_ids"]


def test_no_eligible_question_means_no_set(conn, learner):
    assert practice.build(conn, learner, "session", "CI-02", 1, False, NOW) is None      # no question on CI-02 yet
    assert conn.execute("select count(*) c from practice_set").fetchone()["c"] == 0
    assert conn.execute("select count(*) c from activity_event").fetchone()["c"] == 0


def test_mock_mode_still_serves_the_examples(mock_client):
    assert mock_client.get("/v1/practice-sets/31").status_code == 200
    assert mock_client.post("/v1/practice-sets/31/complete").status_code == 200
