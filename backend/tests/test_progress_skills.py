"""Tiến độ · Năng lực: counted from the learner's own records; nothing is predicted."""
import json
import re

from app.schemas.progress import ProgressSkills
from tests.conftest import answer_all, make_wrong_unit_answer

FORM = "de-thi-thu-1"
PREDICTION = re.compile(r"dự đoán|xác suất|khả năng đỗ|khả năng đậu|điểm dự kiến|xu hướng", re.IGNORECASE)


def skills(client, **params) -> dict:
    r = client.get("/v1/progress/skills", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def sit(client, clock, wrong: int = 0, form: str = FORM) -> dict:
    attempt = client.post(f"/v1/exams/{form}/attempts", json={}).json()
    answer_all(client, attempt, wrong=wrong)
    clock.advance(minutes=1)
    return client.post(f"/v1/attempts/{attempt['attempt_id']}/submit").json()


def keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys(v)}
    return set()


def test_a_new_learner_gets_empty_blocks_not_invented_ones(learner_api):
    body = skills(learner_api)
    ProgressSkills.model_validate(body)
    assert body["scope"] == "latest3" and body["days_to_exam"] == 156      # 10/10/2026 to 15/03/2027
    assert (body["coverage"]["assessed_topics"], body["coverage"]["total_topics"]) == (0, 54)
    assert [m["module_id"] for m in body["coverage"]["modules"]] == [f"g{n}" for n in range(1, 9)]
    assert [m["topics_total"] for m in body["coverage"]["modules"]] == [5, 11, 3, 8, 2, 19, 3, 3]
    assert [(p["rank"], p["competency_code"], p["total"], p["weakest_vi"]) for p in body["priorities"]] == [
        (1, "CI-01", 0, None), (2, "CI-04", 0, None), (3, "FND", 0, None)]      # the topics that have questions
    assert body["mock_scores"] == [] and body["group_grid"] is None
    assert [(lv["level"], lv["label_vi"], lv["total"]) for lv in body["levels"]] == [
        (1, "Nhớ, Hiểu", 0), (2, "Vận dụng", 0), (3, "Phân tích, Đánh giá", 0)]


def test_a_finished_mock_shows_its_real_score_and_what_it_assessed(learner_api, clock):
    results = sit(learner_api, clock, wrong=2)
    body = skills(learner_api)
    assert body["mock_scores"] == [{"attempt_id": results["attempt_id"], "title": "Đề thi thử số 1",
                                    "submitted_at": results["submitted_at"], "score": 8, "total": 10}]
    assert sum(lv["total"] for lv in body["levels"]) == 10 and sum(lv["correct"] for lv in body["levels"]) == 8
    assert body["coverage"]["assessed_topics"] == 1                         # CI-04: three answers. CI-01: one. FND is not a core issue
    assert body["coverage"]["modules"][0]["topics_assessed"] == 1
    answered = {p["competency_code"]: p["total"] for p in body["priorities"]}
    assert sum(answered.values()) == 10 and answered["FND"] == 6


def test_the_scope_chooses_which_mocks_count(learner_api, clock):
    ids = [sit(learner_api, clock)["attempt_id"] for _ in range(4)]
    sit(learner_api, clock, form="danh-gia-nang-luc")                       # the diagnostic is not a mock score
    assert [s["attempt_id"] for s in skills(learner_api)["mock_scores"]] == ids[1:]         # the last three, oldest first
    everything = skills(learner_api, scope="all")
    assert [s["attempt_id"] for s in everything["mock_scores"]] == ids and everything["scope"] == "all"
    assert sum(lv["total"] for lv in skills(learner_api)["levels"]) == 30
    assert sum(lv["total"] for lv in everything["levels"]) == 40


def test_a_priority_names_the_unit_with_most_wrong_answers(learner_api):
    make_wrong_unit_answer(learner_api)
    fnd = next(p for p in skills(learner_api)["priorities"] if p["competency_code"] == "FND")
    assert (fnd["correct"], fnd["total"], fnd["weakest_vi"]) == (0, 1, "Đo lường tần suất bệnh")


def test_nothing_in_the_payload_predicts_the_exam(learner_api, clock):
    sit(learner_api, clock, wrong=3)
    make_wrong_unit_answer(learner_api)
    body = skills(learner_api, scope="all")
    assert not PREDICTION.search(json.dumps(body, ensure_ascii=False))
    assert not [k for k in keys(body) if re.search(r"predict|forecast|pass|trend|probab", k)]


def test_the_exam_date_gone_by_counts_as_zero_days(learner_api, conn):
    conn.execute("update learner set exam_date = '2026-10-01'")
    conn.commit()
    assert skills(learner_api)["days_to_exam"] == 0


def test_another_learner_sees_only_their_own_records(api, learner_api, clock, tokens_for_new_learner):
    sit(learner_api, clock, wrong=2)
    other = api.get("/v1/progress/skills", headers=tokens_for_new_learner()).json()
    assert other["mock_scores"] == [] and other["coverage"]["assessed_topics"] == 0
    assert all(p["total"] == 0 for p in other["priorities"])


def test_an_unknown_scope_is_refused_and_mock_mode_answers(learner_api, mock_client):
    assert learner_api.get("/v1/progress/skills", params={"scope": "week"}).status_code == 422
    assert mock_client.get("/v1/progress/skills").status_code == 200
