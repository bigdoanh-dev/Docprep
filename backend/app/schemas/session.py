"""Phiên hôm nay: the daily session, built once per local day by rules."""
from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import Schema, with_example


class SessionStep(Schema):
    kind: Literal["cards", "practice", "continue"]
    count: int
    minutes: int
    reason_vi: str = Field(description='One line built from the rule inputs ("Vì sao thứ tự này?").')
    done: bool
    practice_set_id: int | None = Field(default=None, description="Set for kind practice.")
    unit_id: str | None = Field(default=None, description="Set for kind continue.")


class SessionToday(Schema):
    """A step with nothing behind it is left out, so there may be fewer than three."""
    local_date: date
    steps: list[SessionStep]
    total_minutes: int

    model_config = with_example({
        "local_date": "2026-10-10",
        "steps": [
            {"kind": "cards", "count": 8, "minutes": 4, "reason_vi": "8 thẻ đến hạn hôm nay, 2 thẻ quá hạn ôn trước.",
             "done": False, "practice_set_id": None, "unit_id": None},
            {"kind": "practice", "count": 6, "minutes": 8,
             "reason_vi": f"Bạn sai 3 câu về {s.Q1_TOPIC} trong 7 ngày qua.",
             "done": False, "practice_set_id": 31, "unit_id": None},
            {"kind": "continue", "count": 4, "minutes": 6,
             "reason_vi": f"Học tiếp học phần đang ưu tiên: {s.MODULES[0][2]}.",
             "done": False, "practice_set_id": None, "unit_id": "u-dt-02"},
        ],
        "total_minutes": 18,
    })
