"""Thi thử under /v1. Ported from the kickoff demo's test_exams_api.py."""
import json
import re

import pytest

from tests.conftest import _issue, answer_all

FORM = "de-thi-thu-1"


def start(client):
    r = client.post(f"/v1/exams/{FORM}/attempts", json={})
    assert r.status_code == 200, r.text
    return r.json()


def forms(client) -> dict:
    return {f["id"]: f for f in client.get("/v1/exams").json()["items"]}


def test_exam_list(learner_api):
    listed = learner_api.get("/v1/exams").json()["items"]
    assert [f["id"] for f in listed] == ["danh-gia-nang-luc", FORM, "de-tu-rap"]
    assert listed[1] == {"id": FORM, "title": "Đề thi thử số 1", "kind": "demo_short", "n_questions": 10,
                         "minutes": 10, "attempts_left": None, "last": None, "open_attempt_id": None,
                         "open_remaining_s": None, "history": [], "plan": None}
    assert (listed[0]["kind"], listed[0]["n_questions"], listed[0]["minutes"]) == ("diagnostic", 6, 6)


def test_start_shuffles_and_hides_answers(learner_api):
    a = start(learner_api)
    assert len(a["questions"]) == 10 and a["remaining_s"] == 600 and a["warning_s"] == 300
    assert a["submitted"] is False and a["answers"] == {} and a["title"] == "Đề thi thử số 1"
    assert [q["n"] for q in a["questions"]] == list(range(1, 11))
    assert all(sorted(o["key"] for o in q["options"]) == ["a", "b", "c", "d"] for q in a["questions"])
    assert "is_correct" not in json.dumps(a) and "rationale" not in json.dumps(a)
    authored = ["q-dt-07", "q-dt-08", "q-dt-09", "q-dt-10", "q-dt-11", "q-dt-12", "q-tc-01", "q-tc-02", "q-tc-03", "q-tc-04"]
    assert sorted(q["id"] for q in a["questions"]) == sorted(authored)


def test_starting_again_resumes_the_open_attempt(learner_api):
    a = start(learner_api)
    assert start(learner_api)["attempt_id"] == a["attempt_id"]
    assert forms(learner_api)[FORM]["open_attempt_id"] == a["attempt_id"]


def test_autosave_resume(learner_api, clock):  # Review Focus 4
    a = start(learner_api)
    q = a["questions"][0]
    key = q["options"][0]["key"]
    r = learner_api.put(f"/v1/attempts/{a['attempt_id']}/answers/{q['id']}", json={"chosen": key, "flagged": True})
    assert r.json() == {"ok": True}
    clock.advance(seconds=90)
    resumed = learner_api.get(f"/v1/attempts/{a['attempt_id']}").json()
    assert resumed["answers"] == {q["id"]: {"chosen": key, "flagged": True}}
    assert resumed["submitted"] is False and resumed["remaining_s"] == 510
    assert [x["id"] for x in resumed["questions"]] == [x["id"] for x in a["questions"]]
    assert resumed["questions"][0]["options"] == q["options"]


def test_autosave_is_idempotent_and_counts_changes(learner_api, conn):
    a = start(learner_api)
    q = a["questions"][0]
    url = f"/v1/attempts/{a['attempt_id']}/answers/{q['id']}"
    k1, k2 = q["options"][0]["key"], q["options"][1]["key"]
    for body in ({"chosen": k1, "flagged": False}, {"chosen": k1, "flagged": False}, {"chosen": k2, "flagged": False},
                 {"chosen": None, "flagged": True}):
        assert learner_api.put(url, json=body).status_code == 200
    row = conn.execute("select chosen, flagged, changes from attempt_answer").fetchall()
    assert row == [{"chosen": None, "flagged": True, "changes": 3}]


def test_autosave_rejects_foreign_question_and_option(learner_api):
    a = start(learner_api)
    base = f"/v1/attempts/{a['attempt_id']}/answers"
    assert learner_api.put(f"{base}/q-dt-01", json={"chosen": "a", "flagged": False}).status_code == 404
    r = learner_api.put(f"{base}/{a['questions'][0]['id']}", json={"chosen": "z", "flagged": False})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_option"


def test_after_deadline_auto_submits_and_blocks_saves(learner_api, clock):  # Review Focus 4
    a = start(learner_api)
    q = a["questions"][0]
    learner_api.put(f"/v1/attempts/{a['attempt_id']}/answers/{q['id']}", json={"chosen": q["options"][0]["key"], "flagged": False})
    clock.advance(seconds=601)
    assert learner_api.get(f"/v1/attempts/{a['attempt_id']}").json()["submitted"] is True
    res = learner_api.put(f"/v1/attempts/{a['attempt_id']}/answers/{q['id']}", json={"chosen": "a", "flagged": False})
    assert res.status_code == 409 and res.json()["error"]["code"] == "attempt_closed"
    results = learner_api.get(f"/v1/attempts/{a['attempt_id']}/results").json()
    assert results["auto_submitted"] is True and results["duration_s"] == 600 and results["blank"] == 9


def test_save_after_deadline_auto_submits_first(learner_api, clock):  # Review Focus 4
    a = start(learner_api)
    clock.advance(seconds=700)
    q = a["questions"][0]
    res = learner_api.put(f"/v1/attempts/{a['attempt_id']}/answers/{q['id']}", json={"chosen": q["options"][0]["key"], "flagged": False})
    assert res.status_code == 409
    assert learner_api.get(f"/v1/attempts/{a['attempt_id']}/results").json()["blank"] == 10


def test_results_blank_wrong_and_cards(learner_api, conn, clock):
    a = start(learner_api)
    answer_all(learner_api, a, wrong=2, blank=1)
    assert learner_api.get(f"/v1/attempts/{a['attempt_id']}/results").status_code == 409
    clock.advance(seconds=125)
    r = learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit").json()
    assert (r["score"], r["wrong"], r["blank"], r["total"], r["new_cards"]) == (7, 2, 1, 10, 2)
    assert r["duration_s"] == 125 and r["auto_submitted"] is False and r["title"] == "Đề thi thử số 1"
    assert [i["status"] for i in r["items"]] == ["wrong", "wrong", "blank"] + ["ok"] * 7
    assert [i["n"] for i in r["items"]] == list(range(1, 11)) and all(i["topic"] for i in r["items"])
    assert len(r["priority_top"]) == 2 and all(isinstance(n, str) for n in r["priority_top"])
    assert learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit").json() == r
    assert learner_api.get(f"/v1/attempts/{a['attempt_id']}/results").json() == r
    assert not re.search(r"(dự đoán|xác suất|khả năng đỗ)", json.dumps(r, ensure_ascii=False))

    assert conn.execute("select count(*) c from item_response where context='mock'").fetchone()["c"] == 9
    assert conn.execute("select count(*) c from card where source_context='mock'").fetchone()["c"] == 2
    listed = forms(learner_api)[FORM]
    assert listed["last"] == {"attempt_id": a["attempt_id"], "score": 7, "total": 10} and listed["open_attempt_id"] is None


def test_review_item_only_after_submit(learner_api):
    a = start(learner_api)
    qid = a["questions"][0]["id"]
    assert learner_api.get(f"/v1/attempts/{a['attempt_id']}/items/{qid}").status_code == 409
    answer_all(learner_api, a, wrong=1)
    learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit")
    item = learner_api.get(f"/v1/attempts/{a['attempt_id']}/items/{qid}").json()
    assert item["n"] == 1 and item["stem"] == a["questions"][0]["stem"]
    assert [o["key"] for o in item["options"]] == [o["key"] for o in a["questions"][0]["options"]]
    assert sum(o["is_correct"] for o in item["options"]) == 1
    chosen = next(o for o in item["options"] if o["key"] == item["chosen"])
    assert chosen["is_correct"] is False and item["explanation"] and item["citations"][0]["passage_id"]
    assert set(item["rationales"]) == {"a", "b", "c", "d"}


def test_unknown_form_and_attempt_are_404(learner_api):
    assert learner_api.post("/v1/exams/nope/attempts", json={}).status_code == 404
    assert learner_api.get("/v1/attempts/999").status_code == 404


def test_results_name_topics_whose_priority_rose(learner_api):  # results show the rank change
    a = start(learner_api)
    answer_all(learner_api, a)  # all correct: "Tiêm phòng/Tiêm chủng" (CI-04, three answers) becomes assessed and strong...
    r = learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit").json()
    # ...so the still-unassessed "Dự phòng HIV" (CI-05), same weight and ranked just below it, overtakes it.
    assert r["priority_moved_up"] == ["Dự phòng HIV"]
    assert r["priority_top"] == ["Bệnh truyền nhiễm có nguy cơ gây dịch", "Bệnh không lây nhiễm phổ biến"]


def test_no_priority_change_reports_an_empty_list(learner_api):
    a = start(learner_api)
    r = learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit").json()  # everything blank: nothing is learned
    assert r["priority_moved_up"] == []


# ---- history with date, time and duration; resuming a running attempt ----

def test_history_lists_every_finished_attempt_newest_first(learner_api, clock, learner):
    first = start(learner_api)
    answer_all(learner_api, first, wrong=3)
    clock.advance(seconds=125)
    learner_api.post(f"/v1/attempts/{first['attempt_id']}/submit")
    clock.advance(hours=2)
    learner_api.headers.update(_issue("learner", learner["id"], clock()))   # the first access token has expired
    second = start(learner_api)
    answer_all(learner_api, second)
    clock.advance(seconds=40)
    learner_api.post(f"/v1/attempts/{second['attempt_id']}/submit")

    history = forms(learner_api)[FORM]["history"]
    assert [h["attempt_id"] for h in history] == [second["attempt_id"], first["attempt_id"]]
    assert history[0] == {"attempt_id": second["attempt_id"], "submitted_at": "2026-10-10T11:02:45Z",
                          "duration_s": 40, "score": 10, "total": 10, "auto_submitted": False}
    assert history[1]["submitted_at"] == "2026-10-10T09:02:05Z" and history[1]["duration_s"] == 125
    assert history[1]["score"] == 7


def test_results_carry_the_submission_time(learner_api, clock):
    a = start(learner_api)
    clock.advance(seconds=30)
    r = learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit").json()
    assert r["submitted_at"] == "2026-10-10T09:00:30Z"
    assert learner_api.get(f"/v1/attempts/{a['attempt_id']}/results").json()["submitted_at"] == r["submitted_at"]


def test_running_attempt_is_offered_for_resume_with_time_left(learner_api, clock):
    a = start(learner_api)
    clock.advance(seconds=200)
    form = forms(learner_api)[FORM]
    assert form["open_attempt_id"] == a["attempt_id"] and form["open_remaining_s"] == 400
    assert form["history"] == []


def test_attempt_left_past_its_deadline_moves_into_history(learner_api, clock):
    a = start(learner_api)
    q = a["questions"][0]
    learner_api.put(f"/v1/attempts/{a['attempt_id']}/answers/{q['id']}", json={"chosen": q["options"][0]["key"], "flagged": False})
    clock.advance(seconds=900)  # the learner never came back before time ran out
    form = forms(learner_api)[FORM]
    assert form["open_attempt_id"] is None
    assert form["history"] == [{"attempt_id": a["attempt_id"], "submitted_at": "2026-10-10T09:10:00Z",
                                "duration_s": 600, "score": form["history"][0]["score"], "total": 10,
                                "auto_submitted": True}]


# ---- starting a new test while one is still running ----

def test_fresh_start_hands_in_the_running_attempt_and_opens_a_new_one(learner_api, clock):
    old = start(learner_api)
    answer_all(learner_api, old, wrong=1, blank=7)  # 1 wrong, 7 blank, 2 correct
    clock.advance(seconds=60)
    r = learner_api.post(f"/v1/exams/{FORM}/attempts", json={"fresh": True})
    assert r.status_code == 200
    new = r.json()
    assert new["attempt_id"] != old["attempt_id"] and new["answers"] == {} and new["remaining_s"] == 600

    form = forms(learner_api)[FORM]
    assert form["open_attempt_id"] == new["attempt_id"]
    assert form["history"] == [{"attempt_id": old["attempt_id"], "submitted_at": "2026-10-10T09:01:00Z",
                                "duration_s": 60, "score": 2, "total": 10, "auto_submitted": False}]
    assert learner_api.get(f"/v1/attempts/{old['attempt_id']}/results").json()["blank"] == 7


def test_fresh_start_with_nothing_running_just_starts(learner_api):
    new = learner_api.post(f"/v1/exams/{FORM}/attempts", json={"fresh": True}).json()
    assert new["submitted"] is False and forms(learner_api)[FORM]["history"] == []


def test_plain_start_still_resumes_the_running_attempt(learner_api):
    a = start(learner_api)
    assert learner_api.post(f"/v1/exams/{FORM}/attempts", json={"fresh": False}).json()["attempt_id"] == a["attempt_id"]
    assert learner_api.post(f"/v1/exams/{FORM}/attempts", json={}).json()["attempt_id"] == a["attempt_id"]


# ---- added with the port ----------------------------------------------------------------------

def test_another_learners_attempt_is_not_found(api, learner_api, tokens_for_new_learner):
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    other = tokens_for_new_learner()
    qid = attempt["questions"][0]["id"]
    for method, path, body in [("GET", f"/v1/attempts/{attempt['attempt_id']}", None),
                               ("POST", f"/v1/attempts/{attempt['attempt_id']}/submit", None),
                               ("GET", f"/v1/attempts/{attempt['attempt_id']}/results", None),
                               ("GET", f"/v1/attempts/{attempt['attempt_id']}/items/{qid}", None),
                               ("PUT", f"/v1/attempts/{attempt['attempt_id']}/answers/{qid}", {"chosen": "a"})]:
        r = api.request(method, path, json=body, headers=other)
        assert r.status_code == 404 and r.json()["error"]["code"] == "attempt_not_found", path
    assert forms(learner_api)[FORM]["open_attempt_id"] == attempt["attempt_id"]      # untouched


def test_the_diagnostic_feeds_mastery_and_labels_its_cards(learner_api, conn):
    attempt = learner_api.post("/v1/exams/danh-gia-nang-luc/attempts", json={}).json()
    answer_all(learner_api, attempt, wrong=1)
    learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    assert conn.execute("select distinct context from item_response").fetchone()["context"] == "diagnostic"
    assert conn.execute("select source_context from card").fetchone()["source_context"] == "diagnostic"
    assert conn.execute("select count(*) c from mastery where n_responses > 0").fetchone()["c"] == 3   # FND, CI-04, CI-01


def test_a_question_retired_mid_attempt_can_still_be_handed_in_and_reviewed(learner_api, conn):
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    answer_all(learner_api, attempt)
    retired = attempt["questions"][0]["id"]
    conn.execute("update question set status = 'retired' where id = %s", (retired,))
    conn.commit()
    assert learner_api.get(f"/v1/attempts/{attempt['attempt_id']}").status_code == 200
    results = learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    assert results.status_code == 200 and results.json()["total"] == 10 and results.json()["score"] == 10
    assert learner_api.get(f"/v1/attempts/{attempt['attempt_id']}/items/{retired}").status_code == 200
    again = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={})
    assert again.status_code == 409 and again.json()["error"]["code"] == "form_unavailable"


def test_the_assembled_form_is_hidden_when_assembly_is_off(learner_api, monkeypatch):
    from app.config import settings
    monkeypatch.setitem(settings()["exam"], "assembled_enabled", False)
    assert "de-tu-rap" not in forms(learner_api)
    r = learner_api.post("/v1/exams/de-tu-rap/attempts", json={})
    assert r.status_code == 404 and r.json()["error"]["code"] == "form_not_found"


def test_starting_and_handing_in_are_logged(learner_api, conn, clock):
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    clock.advance(seconds=90)
    learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    rows = conn.execute("select kind, duration_ms from activity_event where kind like 'exam_%' order by id").fetchall()
    assert rows == [{"kind": "exam_started", "duration_ms": None}, {"kind": "exam_submitted", "duration_ms": 90_000}]


def test_the_hand_in_at_the_deadline_is_kept_although_the_save_answers_409(learner_api, conn, clock):
    attempt = start(learner_api)
    clock.advance(seconds=700)
    q = attempt["questions"][0]
    r = learner_api.put(f"/v1/attempts/{attempt['attempt_id']}/answers/{q['id']}",
                        json={"chosen": q["options"][0]["key"]}, headers={"Idempotency-Key": "late"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "attempt_closed"
    row = conn.execute("select submitted_at, deadline_at, auto_submitted from exam_attempt").fetchone()
    assert row["auto_submitted"] is True and row["submitted_at"] == row["deadline_at"]
    assert conn.execute("select count(*) c from attempt_answer").fetchone()["c"] == 0
    assert conn.execute("select count(*) c from idempotency_key").fetchone()["c"] == 0


def test_a_save_repeated_with_the_same_key_counts_one_change(learner_api, conn):
    attempt = start(learner_api)
    q = attempt["questions"][0]
    url, key = f"/v1/attempts/{attempt['attempt_id']}/answers/{q['id']}", {"Idempotency-Key": "s1"}
    first, second = q["options"][0]["key"], q["options"][1]["key"]
    assert learner_api.put(url, json={"chosen": first}, headers=key).json() == {"ok": True}
    assert learner_api.put(url, json={"chosen": second}).json() == {"ok": True}              # the learner moved on
    assert learner_api.put(url, json={"chosen": first}, headers=key).json() == {"ok": True}   # the late retry of save 1
    assert conn.execute("select chosen, changes from attempt_answer").fetchone() == {"chosen": second, "changes": 2}
    assert conn.execute("select count(*) c from idempotency_key").fetchone()["c"] == 1


@pytest.mark.parametrize("path", ["/v1/exams", "/v1/attempts/12", "/v1/attempts/12/results"])
def test_mock_mode_still_serves_the_examples(mock_client, path):
    assert mock_client.get(path).status_code == 200
