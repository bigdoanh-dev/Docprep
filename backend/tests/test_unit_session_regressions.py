"""Hồi quy lỗi tạo trùng phiên và gửi lại thao tác kết thúc lượt học."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from app.db import connect
from app.services import units
from tests.conftest import test_database_url, walk_unit


def test_parallel_first_open_has_one_pass(conn, learner, clock):
    conn.commit()
    def open_one(_):
        with connect(test_database_url()) as c:
            return units.next_item(c, learner, "u-dt-01", clock())["session_id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(open_one, range(8)))
    assert len(set(ids)) == 1
    assert conn.execute("select count(*) n from unit_session").fetchone()["n"] == 1


def test_terminal_advance_retry_does_not_start_another_pass(learner_api, conn):
    done = walk_unit(learner_api, "u-dt-01")
    for _ in range(2):
        r = learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-q3"})
        assert r.status_code == 200 and r.json() == done
    assert conn.execute("select count(*) n from unit_session").fetchone()["n"] == 1
    reopened = learner_api.get("/v1/units/u-dt-01/next").json()
    assert reopened["position"] == 0 and reopened["session_id"] != done["session_id"]


def test_advance_key_replays_even_after_explicit_reopen(learner_api):
    first = learner_api.get("/v1/units/u-dt-01/next").json()
    headers = {"Idempotency-Key": str(uuid4())}
    data = {"unit_item_id": first["item"]["unit_item_id"]}
    one = learner_api.post("/v1/units/u-dt-01/advance", json=data, headers=headers)
    walk_unit(learner_api, "u-dt-01")
    learner_api.get("/v1/units/u-dt-01/next")
    assert learner_api.post("/v1/units/u-dt-01/advance", json=data, headers=headers).json() == one.json()
