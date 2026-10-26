"""Học phần and the unit flow under /v1. Ported from the kickoff demo's test_practice_api.py."""
import json

import pytest

from tests.conftest import make_wrong_unit_answer, walk_unit


def test_first_item_is_content_with_citation(learner_api):
    v = learner_api.get("/v1/units/u-dt-01/next").json()
    assert v["item"]["unit_item_id"] == "u1-c1" and v["item"]["kind"] == "content"
    assert v["item"]["title"] == "Tỷ lệ hiện mắc" and "đang mắc bệnh" in v["item"]["body"]
    assert v["item"]["citations"][0]["passage_id"] == "dt-p01" and v["item"]["citations"][0]["page"] == 58
    assert (v["position"], v["total"], v["done"], v["cards_created"]) == (0, 6, False, 0)
    assert v["topic"] == "Đo lường tần suất bệnh"


def test_unit_flow_wrong_answer_inserts_remediation_and_card(learner_api, conn):
    learner_api.get("/v1/units/u-dt-01/next")
    v = learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"}).json()
    q = v["item"]["question"]
    assert q["id"] == "q-dt-01" and [o["key"] for o in q["options"]] == ["a", "b", "c", "d"]
    assert "is_correct" not in json.dumps(v) and "rationale" not in json.dumps(v)

    r = learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q1", "chosen": "b"}).json()
    assert r["correct"] is False and r["correct_key"] == "a" and r["remediation_inserted"] and r["card_created"]
    assert r["remediation_note"] == "Đã thêm 1 ví dụ vào lộ trình vì bạn chọn 5% — hãy xem lại mẫu số."
    assert r["explanation"].startswith("50 ÷ 2.000 = 2,5%") and set(r["rationales"]) == {"a", "b", "c", "d"}
    assert r["citations"][0]["passage_id"] == "dt-p01"

    v = learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-q1"}).json()
    assert v["item"]["kind"] == "remediation" and v["item"]["reason"] == "Được thêm vì bạn chọn 5% ở câu trước"
    assert v["item"]["title"] == "Ví dụ · Tính từng bước" and v["total"] == 7 and v["position"] == 2
    kinds = [r["kind"] for r in conn.execute("select kind from activity_event order by id")]
    assert kinds == ["unit_response", "cards_created", "remediation_inserted"]


def test_correct_answer_inserts_nothing(learner_api):
    learner_api.get("/v1/units/u-dt-01/next")
    learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    r = learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q1", "chosen": "a"}).json()
    assert r["correct"] and not r["remediation_inserted"] and not r["card_created"] and r["remediation_note"] is None
    v = learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-q1"}).json()
    assert v["item"]["unit_item_id"] == "u1-c2" and v["total"] == 6


def test_double_check_is_idempotent(learner_api, conn):
    a = make_wrong_unit_answer(learner_api)
    b = learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q1", "chosen": "b"}).json()
    assert a == b
    assert conn.execute("select count(*) c from item_response").fetchone()["c"] == 1
    assert conn.execute("select count(*) c from card").fetchone()["c"] == 1
    assert conn.execute("select n_responses from mastery where competency_code='FND'").fetchone()["n_responses"] == 1
    assert conn.execute("select queue from unit_session").fetchone()["queue"].count("u1-r1") == 1


def test_double_advance_moves_once(learner_api):
    learner_api.get("/v1/units/u-dt-01/next")
    learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    v = learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"}).json()
    assert v["item"]["unit_item_id"] == "u1-q1" and v["position"] == 1


def test_reload_shows_feedback_for_answered_item(learner_api):
    answered = make_wrong_unit_answer(learner_api)
    v = learner_api.get("/v1/units/u-dt-01/next").json()
    assert v["item"]["unit_item_id"] == "u1-q1" and v["item"]["feedback"] == answered and v["item"]["chosen"] == "b"


def test_answer_must_be_for_the_current_quiz_item_and_a_real_option(learner_api):
    learner_api.get("/v1/units/u-dt-01/next")
    r = learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q2", "chosen": "a"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_current_item"
    learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    r = learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q1", "chosen": "z"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_option"
    r = learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-c1", "chosen": "a"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "item_not_found"


def test_end_of_unit_reports_cards(learner_api):
    v = walk_unit(learner_api, "u-dt-01", wrong={"u1-q1": "b"})
    assert v["done"] is True and v["cards_created"] == 1 and v["item"] is None and v["position"] == v["total"] == 7


def test_skipping_a_quiz_creates_no_response(learner_api, conn):
    learner_api.get("/v1/units/u-dt-01/next")
    learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    v = learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-q1"}).json()
    assert v["item"]["unit_item_id"] == "u1-c2"
    assert conn.execute("select count(*) c from item_response").fetchone()["c"] == 0


def test_unknown_unit_is_404(learner_api):
    r = learner_api.get("/v1/units/nope/next")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unit_not_found"


def test_modules_list_and_detail(learner_api):
    ms = {m["id"]: m for m in learner_api.get("/v1/modules").json()["items"]}
    assert list(ms)[0] == "g1"
    assert (ms["g1"]["coming_soon"], ms["g1"]["units_total"], ms["g1"]["units_done"]) == (False, 2, 0)
    assert ms["g3"]["coming_soon"] is True and ms["g2"]["units_total"] == 0
    walk_unit(learner_api, "u-dt-01")
    assert learner_api.get("/v1/modules").json()["items"][0]["units_done"] == 1
    detail = learner_api.get("/v1/modules/g1").json()
    assert detail["short_name"] == "Sức khỏe quần thể và dự phòng"
    assert detail["units"] == [{"id": "u-dt-01", "topic": "Đo lường tần suất bệnh", "done": True},
                               {"id": "u-dt-02", "topic": "Đo lường kết hợp và sàng lọc", "done": False}]
    r = learner_api.get("/v1/modules/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "module_not_found"


# ---- added with the port ----------------------------------------------------------------------

def test_the_eight_hoc_phan_are_listed_in_blueprint_order(learner_api):
    items = learner_api.get("/v1/modules").json()["items"]
    assert [m["id"] for m in items] == [f"g{n}" for n in range(1, 9)]
    assert items[0] == {"id": "g1", "name": "Vấn đề sức khỏe quần thể cần can thiệp ở cấp ban đầu để ngăn ngừa tiến triển",
                        "short_name": "Sức khỏe quần thể và dự phòng", "core_issue_group": 1, "coming_soon": False,
                        "units_total": 2, "units_done": 0, "topics_total": 5}
    assert all(m["coming_soon"] and m["units_total"] == 0 for m in items[1:])


@pytest.mark.parametrize("params,expected", [
    ({"q": "truyen nhiem"}, ["g4"]),
    ({"q": "Sức khỏe"}, ["g1", "g2", "g5", "g6", "g7"]),
    ({"group": 6}, ["g6"]),
    ({"core_issue": 20}, ["g4"]),
    ({"level": 3}, ["g1"]),
    ({"status": "not_started"}, [f"g{n}" for n in range(1, 9)]),
    ({"status": "done"}, []),
    ({"group": 6, "q": "truyen nhiem"}, []),
])
def test_filters(learner_api, params, expected):
    assert [m["id"] for m in learner_api.get("/v1/modules", params=params).json()["items"]] == expected


def test_status_follows_the_learners_progress(learner_api):
    learner_api.get("/v1/units/u-dt-01/next")
    assert [m["id"] for m in learner_api.get("/v1/modules", params={"status": "in_progress"}).json()["items"]] == ["g1"]
    walk_unit(learner_api, "u-dt-01")
    walk_unit(learner_api, "u-dt-02")
    assert [m["id"] for m in learner_api.get("/v1/modules", params={"status": "done"}).json()["items"]] == ["g1"]
    assert "g1" not in [m["id"] for m in learner_api.get("/v1/modules", params={"status": "not_started"}).json()["items"]]


def test_another_learners_unit_session_is_not_resumed(api, learner_api, tokens_for_new_learner):
    learner_api.get("/v1/units/u-dt-01/next")
    learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    other = api.get("/v1/units/u-dt-01/next", headers=tokens_for_new_learner())
    assert other.json()["position"] == 0
    assert other.json()["session_id"] != learner_api.get("/v1/units/u-dt-01/next").json()["session_id"]
    assert api.get("/v1/modules", params={"status": "in_progress"}, headers=tokens_for_new_learner()).json()["items"] == []


def test_a_repeated_answer_with_the_same_key_writes_once(learner_api, conn):
    learner_api.get("/v1/units/u-dt-01/next")
    learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    body, key = {"unit_item_id": "u1-q1", "chosen": "b", "time_ms": 30_000}, {"Idempotency-Key": "abc"}
    first = learner_api.post("/v1/units/u-dt-01/responses", json=body, headers=key).json()
    assert learner_api.post("/v1/units/u-dt-01/responses", json=body, headers=key).json() == first
    assert conn.execute("select count(*) c from item_response").fetchone()["c"] == 1
    assert conn.execute("select count(*) c from idempotency_key").fetchone()["c"] == 1
    assert conn.execute("select duration_ms from activity_event where kind = 'unit_response'").fetchone()["duration_ms"] == 30_000


def test_mock_mode_still_serves_the_examples(mock_client):
    assert mock_client.get("/v1/modules").status_code == 200
    assert mock_client.get("/v1/units/u-dt-01/next").status_code == 200
