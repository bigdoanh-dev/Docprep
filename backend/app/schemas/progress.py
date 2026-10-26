"""Tiến độ: Năng lực (what the learner knows) and Nhịp học (how they study).

Nothing here predicts an exam outcome: no predicted score, pass line or trend direction (FR-LRN-26).
"""
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import Schema, with_example

_TODAY = date(2026, 10, 10)
_PATTERN = [0, 15, 30, 0, 45, 20, 10]
_HEATMAP = [{"date": (_TODAY - timedelta(days=55 - i)).isoformat(), "minutes": _PATTERN[i % 7]} for i in range(56)]
_FORECAST = [{"date": (_TODAY + timedelta(days=i)).isoformat(), "count": n}
             for i, n in enumerate([12, 5, 9, 3, 7, 4, 6])]


class ModuleCoverage(Schema):
    module_id: str
    short_name: str
    topics_assessed: int
    topics_total: int


class Coverage(Schema):
    assessed_topics: int
    total_topics: int
    modules: list[ModuleCoverage]


class PriorityTopic(Schema):
    rank: int
    competency_code: str
    name: str
    module_id: str
    correct: int
    total: int
    weakest_vi: str | None = None


class MockScore(Schema):
    """A real score from a finished mock attempt."""
    attempt_id: int
    title: str
    submitted_at: datetime
    score: int
    total: int


class GridCell(Schema):
    correct: int
    total: int


class GridExam(Schema):
    attempt_id: int
    label: str


class GridRow(Schema):
    group_id: int
    name: str
    cells: list[GridCell | None] = Field(description="One per exam, in the order of `exams`; null when no item.")
    pooled: GridCell


class GroupGrid(Schema):
    exams: list[GridExam]
    rows: list[GridRow] = Field(description="The eight core-issue groups.")


class LevelAccuracy(Schema):
    level: Literal[1, 2, 3]
    label_vi: str
    correct: int
    total: int


class ProgressSkills(Schema):
    days_to_exam: int
    scope: Literal["latest3", "all"]
    coverage: Coverage
    priorities: list[PriorityTopic] = Field(max_length=3)
    mock_scores: list[MockScore]
    group_grid: GroupGrid | None = Field(default=None, description="Present only when the grid is switched on.")
    levels: list[LevelAccuracy]

    model_config = with_example({
        "days_to_exam": 142,
        "scope": "latest3",
        "coverage": {
            "assessed_topics": 2, "total_topics": 54,
            "modules": [{"module_id": mid, "short_name": short, "topics_assessed": 2 if i == 0 else 0,
                         "topics_total": s.GROUP_SIZES[i]} for i, (mid, _name, short) in enumerate(s.MODULES)],
        },
        "priorities": [
            {"rank": 1, "competency_code": "FND", "name": "Khái niệm cơ bản của y học dự phòng", "module_id": "g1",
             "correct": 4, "total": 8, "weakest_vi": s.Q1_TOPIC},
            {"rank": 2, "competency_code": "CI-04", "name": "Tiêm phòng/Tiêm chủng trẻ em và người lớn",
             "module_id": "g1", "correct": 3, "total": 5, "weakest_vi": None},
            {"rank": 3, "competency_code": "CI-01", "name": "Bệnh truyền nhiễm có nguy cơ gây dịch",
             "module_id": "g1", "correct": 2, "total": 3, "weakest_vi": None},
        ],
        "mock_scores": [
            {"attempt_id": 3, "title": "Đề thi thử số 1", "submitted_at": "2026-09-28T03:50:00Z", "score": 29,
             "total": 40},
            {"attempt_id": 4, "title": "Đề thi thử số 1", "submitted_at": "2026-10-06T03:48:00Z", "score": 33,
             "total": 40},
        ],
        "group_grid": None,
        "levels": [
            {"level": 1, "label_vi": "Nhớ, Hiểu", "correct": 12, "total": 15},
            {"level": 2, "label_vi": "Vận dụng", "correct": 19, "total": 32},
            {"level": 3, "label_vi": "Phân tích, Đánh giá", "correct": 4, "total": 9},
        ],
    })


class WeekTime(Schema):
    minutes: int
    previous_minutes: int
    study_days: int
    days_elapsed: int


class DayMinutes(Schema):
    date: date
    minutes: int


class MemoryStats(Schema):
    recall_rate: float | None = Field(default=None, ge=0, le=1, description="Null until there are reviews.")
    window_days: int
    reviews: int
    new: int
    learning: int
    mastered: int
    due_today: int


class CurvePoint(Schema):
    """A point of the memory curve, from the learner's real review dates. It illustrates the mechanism."""
    date: date
    recall: float = Field(ge=0, le=1)
    kind: Literal["review", "decay", "projected"]


class ModuleRecall(Schema):
    module_id: str
    short_name: str
    now: float = Field(ge=0, le=1)
    in_7_days: float = Field(ge=0, le=1, description="Without any review in between.")


class DueDay(Schema):
    date: date
    count: int


class ActivityEntry(Schema):
    kind: Literal["unit", "practice", "chat", "cards", "exam"]
    title: str
    occurred_at: datetime
    minutes: int | None = None
    result_vi: str | None = None


class ProgressRhythm(Schema):
    days_to_exam: int
    week: WeekTime
    heatmap: list[DayMinutes] = Field(description="The last 8 weeks, one entry per day, oldest first.")
    memory: MemoryStats
    curve: list[CurvePoint]
    recall_by_module: list[ModuleRecall]
    due_forecast: list[DueDay] = Field(description="The next 7 days, today first.")
    activity: list[ActivityEntry] = Field(description="This week, newest first.")

    model_config = with_example({
        "days_to_exam": 142,
        "week": {"minutes": 200, "previous_minutes": 165, "study_days": 5, "days_elapsed": 6},
        "heatmap": _HEATMAP,
        "memory": {"recall_rate": 0.86, "window_days": 30, "reviews": 214, "new": 18, "learning": 24,
                   "mastered": 62, "due_today": 12},
        "curve": [
            {"date": "2026-09-20", "recall": 1.0, "kind": "review"},
            {"date": "2026-09-27", "recall": 0.9, "kind": "decay"},
            {"date": "2026-09-27", "recall": 1.0, "kind": "review"},
            {"date": "2026-10-10", "recall": 0.9, "kind": "decay"},
            {"date": "2026-10-17", "recall": 0.78, "kind": "projected"},
        ],
        "recall_by_module": [
            {"module_id": s.MODULES[0][0], "short_name": s.MODULES[0][2], "now": 0.93, "in_7_days": 0.85},
        ],
        "due_forecast": _FORECAST,
        "activity": [
            {"kind": "unit", "title": f"{s.MODULES[0][2]} · {s.Q1_TOPIC}", "occurred_at": "2026-10-09T12:40:00Z",
             "minutes": 14, "result_vi": "Hoàn thành"},
            {"kind": "practice", "title": f"Luyện điểm yếu: {s.Q1_TOPIC}", "occurred_at": "2026-10-09T12:20:00Z",
             "minutes": 8, "result_vi": "4/6"},
            {"kind": "chat", "title": "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?",
             "occurred_at": "2026-10-08T08:12:00Z", "minutes": None, "result_vi": None},
            {"kind": "cards", "title": "Ôn 23 thẻ", "occurred_at": "2026-10-07T13:05:00Z", "minutes": 11,
             "result_vi": "20/23"},
            {"kind": "exam", "title": "Đề thi thử số 1", "occurred_at": "2026-10-06T03:48:00Z", "minutes": 48,
             "result_vi": "33/40"},
        ],
    })
