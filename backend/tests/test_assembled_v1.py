"""Ported from the kickoff demo's test_assembled_api.py."""
"""The assembled exam ("Đề tự ráp"): chosen per learner from results, completed content and Elo."""
from tests.conftest import _test_conn, answer_all, correct_key, walk_unit, wrong_key

AUTO = "de-tu-rap"
FIXED = "de-thi-thu-1"


def forms(client):
    return {f["id"]: f for f in client.get("/v1/exams").json()["items"]}


def sit_fixed_form(client, wrong):
    """Take the fixed form. `wrong` is a number (the first questions shown) or a set of question ids."""
    a = client.post(f"/v1/exams/{FIXED}/attempts", json={}).json()
    if isinstance(wrong, int):
        answer_all(client, a, wrong=wrong)
    else:
        with _test_conn() as c:
            for q in a["questions"]:
                key = wrong_key(c, q["id"]) if q["id"] in wrong else correct_key(c, q["id"])
                client.put(f"/v1/attempts/{a['attempt_id']}/answers/{q['id']}", json={"chosen": key, "flagged": False})
    results = client.post(f"/v1/attempts/{a['attempt_id']}/submit").json()
    return {s: [i["question_id"] for i in results["items"] if i["status"] == s] for s in ("ok", "wrong")}


def test_list_shows_both_forms_and_a_plan_for_the_assembled_one(learner_api):
    f = forms(learner_api)
    assert list(f) == ["danh-gia-nang-luc", FIXED, AUTO]
    assert f[FIXED]["plan"] is None and f[FIXED]["kind"] == "demo_short"
    auto = f[AUTO]
    assert (auto["kind"], auto["n_questions"], auto["minutes"]) == ("assembled", 10, 10)
    assert auto["plan"]["composition"] == {"new": 10, "wrong": 0, "review": 0}
    assert sum(t["count"] for t in auto["plan"]["topics"]) == 10


def test_first_assembled_exam_follows_the_blueprint_with_new_questions(learner_api, conn):
    a = learner_api.post(f"/v1/exams/{AUTO}/attempts", json={}).json()
    ids = [q["id"] for q in a["questions"]]
    assert len(ids) == len(set(ids)) == 10 and a["remaining_s"] == 600 and a["title"] == "Đề tự ráp"
    assert "is_correct" not in str(a)
    assert conn.execute("select count(*) c from question where id = any(%s) and status = 'approved'", (ids,)).fetchone()["c"] == 10
    per_topic = {r["competency_code"]: r["n"] for r in conn.execute(
        "select competency_code, count(*) as n from question where id = any(%s) group by 1", (ids,))}
    # shares: weight x 0.5 (unassessed) x 0.5 (content not completed) = FND 0.5, CI-04 0.9, CI-01 0.9
    assert per_topic == {"FND": 2, "CI-04": 4, "CI-01": 4}


def test_after_a_test_the_next_one_mixes_new_wrong_and_review(learner_api):
    # four wrong answers across the three topics, six correct
    done = sit_fixed_form(learner_api, wrong={"q-dt-07", "q-dt-10", "q-tc-01", "q-tc-04"})
    plan = forms(learner_api)[AUTO]["plan"]
    assert plan["composition"] == {"new": 5, "wrong": 3, "review": 2}
    a = learner_api.post(f"/v1/exams/{AUTO}/attempts", json={}).json()
    ids = {q["id"] for q in a["questions"]}
    assert len(ids & set(done["wrong"])) == 3 and len(ids & set(done["ok"])) == 2
    assert len(ids - set(done["wrong"]) - set(done["ok"])) == 5


def test_plan_shown_beforehand_is_what_the_attempt_gets(learner_api, conn):
    sit_fixed_form(learner_api, wrong=3)
    plan = forms(learner_api)[AUTO]["plan"]
    a = learner_api.post(f"/v1/exams/{AUTO}/attempts", json={}).json()
    stored = conn.execute("select assembly from exam_attempt where id = %s", (a["attempt_id"],)).fetchone()["assembly"]
    assert stored["composition"] == plan["composition"]
    assert sum(stored["topics"].values()) == 10


def test_unit_quiz_results_count_too(learner_api):
    walk_unit(learner_api, "u-dt-01", wrong={"u1-q1": "b"})   # q-dt-01 wrong; q-dt-02, q-dt-03 correct
    a = learner_api.post(f"/v1/exams/{AUTO}/attempts", json={}).json()
    ids = {q["id"] for q in a["questions"]}
    assert "q-dt-01" in ids                                   # the question answered wrong comes back
    assert forms(learner_api)[AUTO]["open_attempt_id"] == a["attempt_id"]


def test_completed_units_mark_their_topics_as_completed(learner_api, conn):
    from app.repo.exams import completed_topics
    from tests.conftest import dev_learner
    learner = dev_learner(conn)
    assert completed_topics(conn, learner["id"]) == set()
    # Give the unit one quiz question of another topic, so both halves of the rule show.
    conn.execute("update unit_item set question_id = 'q-tc-01' where id = 'u2-q1'")
    conn.commit()
    walk_unit(learner_api, "u-dt-02")
    conn.rollback()
    # the unit's own topic (FND) plus the topic of a quiz question it contains (q-tc-01 is CI-04)
    assert completed_topics(conn, learner["id"]) == {"FND", "CI-04"}


def test_each_new_assembled_test_avoids_what_was_just_asked(learner_api):
    first = learner_api.post(f"/v1/exams/{AUTO}/attempts", json={}).json()
    answer_all(learner_api, first)                                  # all correct → all ten become review questions
    learner_api.post(f"/v1/attempts/{first['attempt_id']}/submit")
    second = learner_api.post(f"/v1/exams/{AUTO}/attempts", json={}).json()
    overlap = {q["id"] for q in first["questions"]} & {q["id"] for q in second["questions"]}
    # With no wrong answers to bring back, their share is split between new and review: 7 new, 3 review.
    # The greedy pick ends at 5 new, 5 review: CI-01 keeps 3 of the 10 places and has one unseen question
    # left, and by then the review places were spent on other topics. A 7/3 split inside the same topic
    # split exists, so 5 is what the current rule gives, not what it must give (open issue 29).
    assert len(overlap) == 5


def test_assembled_exam_scores_and_lists_like_any_other(learner_api):
    a = learner_api.post(f"/v1/exams/{AUTO}/attempts", json={}).json()
    answer_all(learner_api, a, wrong=2, blank=1)
    r = learner_api.post(f"/v1/attempts/{a['attempt_id']}/submit").json()
    assert (r["score"], r["wrong"], r["blank"], r["total"], r["new_cards"]) == (7, 2, 1, 10, 2)
    history = forms(learner_api)[AUTO]["history"]
    assert [h["attempt_id"] for h in history] == [a["attempt_id"]] and history[0]["total"] == 10
    assert forms(learner_api)[FIXED]["history"] == []
