"""Luyện tập: học phần (the eight blueprint groups) and their units."""
from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import Schema, with_example


class ModuleCard(Schema):
    id: str
    name: str = Field(description="Official name of the blueprint group.")
    short_name: str = Field(description="Display name short enough for a phone card.")
    core_issue_group: int | None = None
    coming_soon: bool
    units_total: int
    units_done: int
    topics_total: int = Field(description="Core issues in this học phần.")


class ModuleList(Schema):
    items: list[ModuleCard]

    model_config = with_example({"items": [
        {"id": mid, "name": name, "short_name": short, "core_issue_group": i + 1, "coming_soon": i > 0,
         "units_total": 2 if i == 0 else 0, "units_done": 1 if i == 0 else 0, "topics_total": s.GROUP_SIZES[i]}
        for i, (mid, name, short) in enumerate(s.MODULES)
    ]})


class UnitSummary(Schema):
    id: str
    topic: str
    done: bool


class ModuleDetail(Schema):
    id: str
    name: str
    short_name: str
    units: list[UnitSummary]

    model_config = with_example({
        "id": s.MODULES[0][0], "name": s.MODULES[0][1], "short_name": s.MODULES[0][2],
        "units": [{"id": "u-dt-01", "topic": s.Q1_TOPIC, "done": True},
                  {"id": "u-dt-02", "topic": "Đo lường kết hợp và sàng lọc", "done": False}],
    })
