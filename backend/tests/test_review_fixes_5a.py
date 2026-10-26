"""Findings of the phase 5A review: every sentence the learner reads must be true when it is shown."""
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app.engine.scheduler import new_state
from app.repo import content
from app.services import practice
from app.services.responses import record_response
from tests.conftest import _issue, correct_key, make_wrong_unit_answer, wrong_key

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)      # the test clock's start: 16:00 in Hà Nội
FND = "Khái niệm cơ bản của y học dự phòng"
CI_04 = "Tiêm phòng/Tiêm chủng trẻ em và người lớn"


def record_wrong(conn, learner, question_id: str, now: datetime = NOW) -> None:
    record_response(conn, learner, content.approved_question(conn, question_id), wrong_key(conn, question_id), "unit", now)
    conn.commit()


def make_set(conn, learner, code: str = "FND", wrong: int = 1) -> dict:
    built = practice.build(conn, learner, "session", code, wrong, False, NOW)
    conn.commit()
    return built


def sign_in_again(client, learner, clock) -> None:
    client.headers.update(_issue("learner", learner["id"], clock()))


def step(body: dict, kind: str) -> dict:
    return next(s for s in body["steps"] if s["kind"] == kind)


def home(client) -> dict:
    return client.get("/v1/home").json()


def answer(client, set_id: int, question_id: str, chosen: str) -> dict:
    r = client.post(f"/v1/practice-sets/{set_id}/responses", json={"question_id": question_id, "chosen": chosen})
    assert r.status_code == 200, r.text
    return r.json()


def approve_new_version(conn, question_id: str, stem: str) -> None:
    """Version 1 is retired and an edited version 2 is approved, by two recorded reviews as the database requires."""
    reviewers = [r["id"] for r in conn.execute("select id from staff_user where is_demo order by id limit 2")]
    conn.execute("update question set status = 'retired' where id = %s and version = 1", (question_id,))
    conn.execute(
        """insert into question(id, version, type, stem, options, explanation, rubric, competency_code, core_issue_id,
             exam_competency_component_id, bloom_level, difficulty_label, difficulty_b, n_responses,
             source_passage_ids, status, ai_assisted, author)
           select id, 2, type, %s, options, explanation, rubric, competency_code, core_issue_id,
                  exam_competency_component_id, bloom_level, difficulty_label, difficulty_b, 0,
                  source_passage_ids, 'in_review_r2', false, author
           from question where id = %s and version = 1""", (stem, question_id))
    for round_, reviewer in enumerate(reviewers, start=1):
        conn.execute("insert into review_decision(target_type, target_id, version, round, reviewer_id, decision) "
                     "values ('question', %s, 2, %s, %s, 'pass')", (question_id, round_, reviewer))
    conn.execute("update question set status = 'approved' where id = %s and version = 2", (question_id,))
    conn.commit()


# ---- C1: nothing is "added to the lộ trình" by a practice answer ----------------------------------

def test_a_wrong_practice_answer_adds_nothing_to_the_learning_path(learner_api, conn, learner, clock):
    home(learner_api)                                                      # visit 1
    clock.advance(minutes=1)
    s = make_set(conn, learner)
    for question_id in ("q-dt-01", "q-dt-02", "q-dt-03"):
        answer(learner_api, s["id"], question_id, wrong_key(conn, question_id))
    assert conn.execute("select count(*) c from activity_event where kind = 'remediation_inserted'").fetchone()["c"] == 0
    clock.advance(minutes=45)
    sign_in_again(learner_api, learner, clock)
    kinds = [x["kind"] for x in home(learner_api)["tutor_suggestions"]]    # visit 2
    assert "example_added" not in kinds and "cards_created" in kinds


# ---- I1: "tomorrow" is about tomorrow's practice, and only about what this set changed -------------

def test_the_summary_names_tomorrows_practice_topic_when_the_set_changed_it(conn, learner):
    record_wrong(conn, learner, "q-dt-01")                                 # before the set, the weak spot is FND
    s = make_set(conn, learner, code="CI-04")
    for question_id in s["question_ids"][:2]:
        practice.answer(conn, learner, s["id"], question_id, wrong_key(conn, question_id), NOW)
    summary = practice.complete(conn, learner, s["id"], NOW)
    assert summary["tomorrow"] == {"reordered": True, "top_item": CI_04}   # two wrong on CI-04 against one on FND


def test_the_summary_is_silent_when_tomorrow_is_the_same(conn, learner):
    record_wrong(conn, learner, "q-dt-01")
    s = make_set(conn, learner)                                            # a set on FND, all answered right
    for question_id in s["question_ids"]:
        practice.answer(conn, learner, s["id"], question_id, correct_key(conn, question_id), NOW)
    assert practice.complete(conn, learner, s["id"], NOW)["tomorrow"] is None


def test_other_work_done_meanwhile_is_not_credited_to_the_set(conn, learner):
    s = make_set(conn, learner)
    first = s["question_ids"][0]
    practice.answer(conn, learner, s["id"], first, correct_key(conn, first), NOW)
    for question_id in ("q-tc-01", "q-tc-02"):                             # elsewhere, two wrong answers on CI-04
        record_wrong(conn, learner, question_id)
    assert practice.complete(conn, learner, s["id"], NOW)["tomorrow"] is None      # CI-04 leads with or without the set


def test_no_tomorrow_line_when_the_learner_pinned_tomorrows_topic(conn, learner):
    record_wrong(conn, learner, "q-dt-01")
    conn.execute("insert into session_addition(learner_id, for_date, competency_code) values (%s, '2026-10-11', 'FND')",
                 (learner["id"],))
    s = make_set(conn, learner, code="CI-04")
    for question_id in s["question_ids"][:2]:
        practice.answer(conn, learner, s["id"], question_id, wrong_key(conn, question_id), NOW)
    assert practice.complete(conn, learner, s["id"], NOW)["tomorrow"] is None


# ---- I2: the cards step is done when its cards were reviewed, and stays done ------------------------

def add_due_cards(conn, learner, n: int) -> None:
    for offset in range(n):
        conn.execute(
            "insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at) "
            "select %s, id, 'unit', stem, 'Đáp án', 'Nguồn', %s, %s from question order by id offset %s limit 1",
            (learner["id"], Jsonb(new_state(NOW)), NOW - timedelta(days=1, minutes=offset), offset))
    conn.commit()


def test_the_cards_step_stays_done_when_a_card_comes_back_or_a_new_one_appears(learner_api, conn, learner, clock):
    add_due_cards(conn, learner, 1)
    record_wrong(conn, learner, "q-dt-10", NOW - timedelta(days=1))        # gives today a practice step (and a card)
    body = learner_api.get("/v1/session/today").json()
    assert step(body, "cards")["count"] == 2
    for card in learner_api.get("/v1/cards/due").json()["items"]:
        learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3})
    assert step(learner_api.get("/v1/session/today").json(), "cards")["done"] is True
    clock.advance(minutes=11)                                              # "Tốt" on a new card: due again in 10 minutes
    assert learner_api.get("/v1/cards/due").json()["total_due"] >= 1
    first = learner_api.get("/v1/session/today/practice").json()["items"][0]["question_id"]
    learner_api.post("/v1/session/today/practice/responses",              # a wrong answer: one more card, due at once
                     json={"question_id": first, "chosen": wrong_key(conn, first)})
    assert step(learner_api.get("/v1/session/today").json(), "cards")["done"] is True
    assert conn.execute("select count(*) c from activity_event where kind = 'session_step_completed' and ref_id = 'cards'").fetchone()["c"] == 1


def test_a_capped_cards_step_is_done_after_its_own_cards(learner_api, conn, learner):
    add_due_cards(conn, learner, 3)
    conn.execute("update learner set max_reviews_per_day = 2")
    conn.commit()
    cards = step(learner_api.get("/v1/session/today").json(), "cards")
    assert cards["reason_vi"] == "2 trong 3 thẻ đến hạn hôm nay, 2 thẻ quá hạn ôn trước." and "card_ids" not in cards
    due = learner_api.get("/v1/cards/due").json()["items"]                 # the longest overdue first: the step's two
    learner_api.post(f"/v1/cards/{due[0]['id']}/reviews", json={"rating": 3})
    assert step(learner_api.get("/v1/session/today").json(), "cards")["done"] is False
    learner_api.post(f"/v1/cards/{due[1]['id']}/reviews", json={"rating": 3})
    assert step(learner_api.get("/v1/session/today").json(), "cards")["done"] is True
    assert conn.execute("select count(*) c from activity_event where kind = 'session_step_completed'").fetchone()["c"] == 1


# ---- I3: an answer sent after midnight belongs to the set the learner is working on -----------------

def test_an_answer_after_midnight_goes_to_the_set_in_progress(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)
    clock.now = datetime(2026, 10, 10, 16, 50, tzinfo=timezone.utc)        # 23:50 in Hà Nội
    sign_in_again(learner_api, learner, clock)
    view = learner_api.get("/v1/session/today/practice").json()
    ids = [i["question_id"] for i in view["items"]]
    post = lambda qid: learner_api.post("/v1/session/today/practice/responses",
                                        json={"question_id": qid, "chosen": correct_key(conn, qid)}, headers={"Idempotency-Key": qid})
    assert post(ids[0]).status_code == 200 and post(ids[1]).status_code == 200
    clock.advance(minutes=20)                                              # 00:10 the next day
    late = post(ids[2])
    assert late.status_code == 200 and late.json()["correct"] is True
    assert post(ids[2]).json() == late.json()                              # the retry of that request is recognised
    assert conn.execute("select count(*) c from daily_session").fetchone()["c"] == 1      # a write builds no session
    assert conn.execute("select count(*) c from item_response where practice_set_id = %s", (view["id"],)).fetchone()["c"] == 3
    summary = learner_api.post("/v1/session/today/practice/complete").json()
    assert summary["graded"] == {"correct": 3, "total": 6}
    today = learner_api.get("/v1/session/today").json()                    # reading builds the new day's session
    assert today["local_date"] == "2026-10-11" and step(today, "practice")["practice_set_id"] != view["id"]


def test_a_write_with_no_session_at_all_is_refused_and_builds_nothing(learner_api, conn):
    r = learner_api.post("/v1/session/today/practice/responses", json={"question_id": "q-dt-01", "chosen": "a"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_practice_today"
    assert learner_api.post("/v1/session/today/practice/complete").json()["error"]["code"] == "no_practice_today"
    assert conn.execute("select count(*) c from daily_session").fetchone()["c"] == 0


# ---- I4: when the worst topic has nothing new to ask, the next one is practised ---------------------

def test_the_next_weak_spot_is_practised_when_the_first_has_no_unseen_question(learner_api, conn, learner):
    for question_id in [r["id"] for r in conn.execute("select id from question where competency_code = 'CI-01' order by id")]:
        record_wrong(conn, learner, question_id)                           # all five CI-01 questions, seen today
    record_wrong(conn, learner, "q-dt-01")
    record_wrong(conn, learner, "q-dt-02")
    body = learner_api.get("/v1/session/today").json()
    assert step(body, "practice")["reason_vi"] == f"Bạn sai 2 câu về {FND} trong 7 ngày qua."
    assert learner_api.get("/v1/session/today/practice").json()["competency_code"] == "FND"


def test_a_pinned_topic_with_nothing_to_ask_falls_back_to_the_weak_spot(learner_api, conn, learner):
    conn.execute("insert into session_addition(learner_id, for_date, competency_code) values (%s, '2026-10-10', 'CI-02')",
                 (learner["id"],))                                         # no question on CI-02 yet
    record_wrong(conn, learner, "q-dt-01")
    assert step(learner_api.get("/v1/session/today").json(), "practice")["reason_vi"] == f"Bạn sai 1 câu về {FND} trong 7 ngày qua."


# ---- I5: an example is tied to the answer only when it was written for that question ----------------

def test_the_topics_example_is_shown_once_and_says_what_it_is(learner_api, conn, learner):
    s = make_set(conn, learner)
    ids = s["question_ids"]                                                # q-dt-01 … q-dt-06
    second = answer(learner_api, s["id"], ids[3], wrong_key(conn, ids[3]))     # q-dt-04: no example of its own
    assert second["remediation"]["title"] == "Ví dụ · Tính từng bước"
    assert second["remediation"]["reason"] == "Ví dụ chung của chủ đề này"
    third = answer(learner_api, s["id"], ids[4], wrong_key(conn, ids[4]))      # the topic's example was shown already
    assert third["remediation"] is None
    own = answer(learner_api, s["id"], ids[0], "b")                           # q-dt-01 has its own example
    assert own["remediation"]["reason"] == "Được thêm vì bạn chọn 5%"
    again = learner_api.get(f"/v1/practice-sets/{s['id']}").json()["items"]
    assert [i["feedback"]["remediation"] is not None for i in again if i["feedback"]] == [True, True, False]


# ---- I6: a withdrawn question leaves an open set; an edited one stays as it was built ---------------

def test_a_question_withdrawn_after_the_set_was_built_is_no_longer_asked(learner_api, conn, learner):
    s = make_set(conn, learner)
    answer(learner_api, s["id"], "q-dt-01", "a")
    conn.execute("update question set status = 'retired' where id in ('q-dt-01', 'q-dt-02')")
    conn.commit()
    view = learner_api.get(f"/v1/practice-sets/{s['id']}").json()
    assert [i["question_id"] for i in view["items"]] == ["q-dt-01", "q-dt-03", "q-dt-04", "q-dt-05", "q-dt-06"]
    assert (view["total"], view["answered"]) == (5, 1)                     # the answered one stays; the unanswered one goes
    r = learner_api.post(f"/v1/practice-sets/{s['id']}/responses", json={"question_id": "q-dt-02", "chosen": "a"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "question_not_in_set"
    assert learner_api.post(f"/v1/practice-sets/{s['id']}/complete").json()["graded"] == {"correct": 1, "total": 5}
    assert conn.execute("select count(*) c from card").fetchone()["c"] == 0


def test_a_question_edited_after_the_set_was_built_is_asked_as_built(learner_api, conn, learner):
    s = make_set(conn, learner)
    old_stem = conn.execute("select stem from question where id = 'q-dt-02' and version = 1").fetchone()["stem"]
    approve_new_version(conn, "q-dt-02", "Câu hỏi đã sửa")
    item = next(i for i in learner_api.get(f"/v1/practice-sets/{s['id']}").json()["items"] if i["question_id"] == "q-dt-02")
    assert item["stem"] == old_stem
    answer(learner_api, s["id"], "q-dt-02", correct_key(conn, "q-dt-02"))
    assert conn.execute("select question_version from item_response").fetchone()["question_version"] == 1


def test_one_answer_per_question_is_also_the_databases_rule(conn, learner):
    import psycopg
    import pytest
    s = make_set(conn, learner)
    question = content.approved_question(conn, "q-dt-01")
    record_response(conn, learner, question, "a", "practice", NOW, practice_set_id=s["id"])
    with pytest.raises(psycopg.errors.UniqueViolation):
        record_response(conn, learner, question, "b", "practice", NOW, practice_set_id=s["id"])
    conn.rollback()


# ---- I7: sentences that stay true ------------------------------------------------------------------

def test_the_unseen_clause_goes_once_the_question_was_answered(learner_api, conn, learner):
    s = make_set(conn, learner)
    answer(learner_api, s["id"], "q-dt-01", "a")
    record_wrong(conn, learner, "q-dt-02", NOW + timedelta(minutes=5))     # answered in a unit after the set was built
    items = {i["question_id"]: i["reason_vi"] for i in learner_api.get(f"/v1/practice-sets/{s['id']}").json()["items"]}
    assert items["q-dt-01"] == items["q-dt-02"] == f"Bạn sai 1 câu về {FND} trong 7 ngày qua."
    assert items["q-dt-03"] == f"Bạn sai 1 câu về {FND} trong 7 ngày qua · bạn chưa gặp câu này trong 14 ngày."


def test_what_happens_during_a_visit_is_listed_at_the_next_one_only(learner_api, conn, clock, learner):
    home(learner_api)                                                      # visit 1
    clock.advance(minutes=45)
    sign_in_again(learner_api, learner, clock)
    assert home(learner_api)["tutor_suggestions"] == []                    # visit 2
    clock.advance(minutes=5)
    make_wrong_unit_answer(learner_api)                                    # during visit 2: a card and an example
    assert home(learner_api)["tutor_suggestions"] == []                    # still visit 2: not news yet
    clock.advance(minutes=45)
    sign_in_again(learner_api, learner, clock)
    assert [x["kind"] for x in home(learner_api)["tutor_suggestions"]] == ["cards_created", "example_added"]    # visit 3
    clock.advance(minutes=45)
    sign_in_again(learner_api, learner, clock)
    assert home(learner_api)["tutor_suggestions"] == []                    # visit 4: listed once


def test_the_practice_line_on_home_is_about_todays_set_only(learner_api, conn, clock, learner):
    home(learner_api)                                                      # visit 1
    clock.advance(minutes=1)
    make_wrong_unit_answer(learner_api)
    clock.advance(days=1)
    sign_in_again(learner_api, learner, clock)
    learner_api.get("/v1/session/today")                                   # yesterday+1: a set is built, Home not opened
    clock.advance(days=8)                                                  # a week later nothing is wrong any more
    sign_in_again(learner_api, learner, clock)
    assert "practice_added" not in [x["kind"] for x in home(learner_api)["tutor_suggestions"]]
