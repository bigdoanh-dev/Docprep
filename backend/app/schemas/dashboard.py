"""Quản lý cấp Bộ · Tổng quan toàn quốc: aggregates for the ministry, read-only.

Aggregates only: no learner is named or identified. A figure that rests on fewer learners than
`suppression_min` is withheld (null), and outcome figures count only learners who consented to
research use. Every score here is a real mock-exam result; nothing forecasts an exam outcome.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import Schema, with_example

Audience = Literal["student", "graduate"]


class FilterOption(Schema):
    value: str
    label_vi: str


class Selected(Schema):
    """The view the figures describe. A filter left out is null: all schools, both audiences, every region."""
    period: str = Field(description="A calendar month in local time, `YYYY-MM`.")
    school: str | None = None
    audience: Audience | None = None
    region: str | None = None


class FilterOptions(Schema):
    periods: list[FilterOption]
    schools: list[FilterOption] = Field(description="A school under the suppression minimum is not offered.")
    audiences: list[FilterOption]
    regions: list[FilterOption]


class ScoreMedian(Schema):
    """A median mock-exam score over consenting learners, as a share of the questions."""
    share: float
    form_size: int | None = Field(
        description="The number of questions when every attempt behind the median has the same; else null.")
    learners: int


class Kpis(Schema):
    active_learners: int
    active_learners_previous: int = Field(description="The month before, for the change.")
    accounts_issued: int
    accounts_activated: int
    practice_items: int = Field(description="Quiz and practice items answered in the period.")
    mock_attempts: int
    mock_median: ScoreMedian | None
    cited_claims_share: float | None
    cited_claims_target: float


class WeekPoint(Schema):
    week_start: date = Field(description="The Monday the week starts on, local time.")
    active_learners: int


class Retention(Schema):
    weeks: Literal[1, 4, 8]
    share: float | None = Field(description="Of learners first active at least that long ago, the share active again "
                                            "in the week that starts that many weeks later.")
    learners: int


class WeeklyActive(Schema):
    weeks: list[WeekPoint]
    retention: list[Retention]


class Alert(Schema):
    """Something a rule found worth attention. The sentences are templates filled with the numbers that triggered it."""
    kind: Literal["low_activation", "slow_review", "old_reports"]
    title_vi: str
    detail_vi: str


class ModuleAccuracy(Schema):
    module_id: str
    short_name: str
    share: float | None = Field(description="Share of mock-exam answers that were correct.")
    low: bool
    learners: int


class AccuracyByModule(Schema):
    learners: int = Field(description="Consenting learners with a mock-exam answer in the period.")
    items: list[ModuleAccuracy]


class QuestionBank(Schema):
    """The whole bank: the school, audience and region filters do not apply to it."""
    approved: int
    in_review: int
    draft: int
    rejected: int
    issues_covered: int = Field(description="Core issues with at least `min_approved_per_issue` approved questions.")
    issues_total: int
    min_approved_per_issue: int
    round1_median_days: float | None
    round2_median_days: float | None
    round2_target_days: int
    rounds_agree_share: float | None = Field(description="Of items decided in round 2, the share where both rounds "
                                                         "reached the same decision.")
    reports_received: int
    reports_resolved: int


class AiSafety(Schema):
    answers: int
    model_versions: list[str]
    corpus_versions: list[str]
    cited_claims_share: float | None = Field(description="Claims that kept a page-level citation after the "
                                                         "post-check, out of the claims checked.")
    cited_claims_target: float
    insufficient_share: float | None
    declined_share: float | None
    flagged_share: float | None = Field(description="Share of answers from which the post-check removed a claim.")
    reports_per_1000: float | None


class ScoreChange(Schema):
    """The median change from a learner's first mock to their latest, among consenting learners with two or more."""
    share: float
    form_size: int | None
    learners: int


class SchoolRow(Schema):
    code: str
    name: str
    region: str | None = Field(description="Null when the school has no region on record.")
    accounts_issued: int
    accounts_activated: int
    activation_low: bool
    weekly_active: float = Field(description="Mean active learners per week over the period.")
    mock_attempts: int
    mock_median: ScoreMedian | None
    first_to_latest: ScoreChange | None


class HiddenSchool(Schema):
    """A school under the suppression minimum: named, counted in the national figures, shown with no figure of its own."""
    name: str
    region: str | None
    learners: int


class Schools(Schema):
    rows: list[SchoolRow]
    hidden: list[HiddenSchool]


class Compliance(Schema):
    chat_p95_ms: int | None
    chat_target_ms: int
    research_consent_learners: int
    research_consent_share: float | None
    consent_withdrawals: int
    deletion_requests: int
    deletion_median_days: float | None


_WEEKS = [58, 66, 75, 86, 107, 126, 145, 163, 177, 188, 196, 202]
_MODULES = [("g1", "Sức khỏe quần thể và dự phòng", 0.71), ("g2", "Cấp cứu và sơ cấp cứu", 0.64),
            ("g3", "Dinh dưỡng và an toàn thực phẩm", 0.58), ("g4", "Bệnh truyền nhiễm", 0.69),
            ("g5", "Sức khỏe nghề nghiệp", 0.80), ("g6", "Sức khỏe cộng đồng và y học gia đình", 0.66),
            ("g7", "Sức khỏe tâm thần và hành vi", 0.52), ("g8", "Giao tiếp và cộng tác", 0.74)]
# code, region, issued, activated, weekly active, attempts, median share, learners behind it, change
_SCHOOLS = [("A", "Miền Bắc", 105, 91, 62.5, 131, 0.70, 58, 0.10), ("B", "Miền Nam", 98, 79, 53.0, 112, 0.675, 51, 0.075),
            ("C", "Miền Bắc", 74, 58, 37.5, 79, 0.675, 36, 0.075), ("D", "Miền Trung", 59, 44, 30.0, 58, 0.65, 27, 0.05),
            ("E", "Miền Nam", 49, 20, 11.5, 26, 0.625, 12, 0.05)]


class AdminOverview(Schema):
    period: str
    computed_at: datetime
    sample_data: bool = Field(description="True when any learner in view is synthetic: the page shows “Dữ liệu mẫu”.")
    suppressed: bool = Field(description="True when the filters select fewer learners than `suppression_min`: "
                                         "every block is then null.")
    suppression_min: int
    selected: Selected
    filters: FilterOptions
    kpis: Kpis | None
    weekly_active: WeeklyActive | None
    alerts: list[Alert]
    accuracy_by_module: AccuracyByModule | None
    question_bank: QuestionBank | None
    ai_safety: AiSafety | None
    schools: Schools | None
    compliance: Compliance | None

    model_config = with_example({
        "period": "2026-09", "computed_at": "2026-10-12T07:32:00Z", "sample_data": True, "suppressed": False,
        "suppression_min": 10,
        "selected": {"period": "2026-09", "school": None, "audience": None, "region": None},
        "filters": {
            "periods": [{"value": "2026-10", "label_vi": "Tháng 10/2026"}, {"value": "2026-09", "label_vi": "Tháng 9/2026"},
                        {"value": "2026-08", "label_vi": "Tháng 8/2026"}],
            "schools": [{"value": f"CSDT-{code}", "label_vi": f"CSĐT {code}"} for code, *_ in _SCHOOLS],
            "audiences": [{"value": "student", "label_vi": "Sinh viên"}, {"value": "graduate", "label_vi": "Đã tốt nghiệp"}],
            "regions": [{"value": r, "label_vi": r} for r in ("Miền Bắc", "Miền Trung", "Miền Nam")],
        },
        "kpis": {
            "active_learners": 241, "active_learners_previous": 204, "accounts_issued": 396, "accounts_activated": 300,
            "practice_items": 13250, "mock_attempts": 412,
            "mock_median": {"share": 0.675, "form_size": 40, "learners": 184},
            "cited_claims_share": 0.972, "cited_claims_target": 0.95,
        },
        "weekly_active": {
            "weeks": [{"week_start": date.fromordinal(date(2026, 7, 20).toordinal() + 7 * i).isoformat(),
                       "active_learners": n} for i, n in enumerate(_WEEKS)],
            "retention": [{"weeks": 1, "share": 0.81, "learners": 290}, {"weeks": 4, "share": 0.62, "learners": 262},
                          {"weeks": 8, "share": 0.48, "learners": 171}],
        },
        "alerts": [
            {"kind": "low_activation", "title_vi": "CSĐT E: mới 41% tài khoản được kích hoạt",
             "detail_vi": "20 / 49 tài khoản · các cơ sở khác 75–87%"},
            {"kind": "slow_review", "title_vi": "Duyệt vòng 2 chậm: trung vị 9 ngày",
             "detail_vi": "Mục tiêu 7 ngày · 60 câu đang chờ"},
            {"kind": "old_reports", "title_vi": "3 báo lỗi của học viên quá 14 ngày chưa xử lý",
             "detail_vi": "2 về câu hỏi, 1 về câu trả lời hỏi đáp"},
        ],
        "accuracy_by_module": {
            "learners": 184,
            "items": [{"module_id": module_id, "short_name": name, "share": share, "low": share < 0.6, "learners": 184}
                      for module_id, name, share in _MODULES],
        },
        "question_bank": {
            "approved": 666, "in_review": 150, "draft": 200, "rejected": 40, "issues_covered": 48, "issues_total": 54,
            "min_approved_per_issue": 10, "round1_median_days": 4.0, "round2_median_days": 9.0, "round2_target_days": 7,
            "rounds_agree_share": 0.81, "reports_received": 41, "reports_resolved": 35,
        },
        "ai_safety": {
            "answers": 3120, "model_versions": ["claude-sonnet-5-5"], "corpus_versions": ["demo-2026-10-09"],
            "cited_claims_share": 0.972, "cited_claims_target": 0.95, "insufficient_share": 0.031,
            "declined_share": 0.004, "flagged_share": 0.012, "reports_per_1000": 1.8,
        },
        "schools": {
            "rows": [{"code": f"CSDT-{code}", "name": f"CSĐT {code}", "region": region, "accounts_issued": issued,
                      "accounts_activated": activated, "activation_low": activated / issued < 0.6,
                      "weekly_active": weekly, "mock_attempts": attempts,
                      "mock_median": {"share": median, "form_size": 40, "learners": learners},
                      "first_to_latest": {"share": change, "form_size": 40, "learners": learners}}
                     for code, region, issued, activated, weekly, attempts, median, learners, change in _SCHOOLS],
            "hidden": [{"name": "CSĐT F", "region": "Tây Nguyên", "learners": 8}],
        },
        "compliance": {
            "chat_p95_ms": 11800, "chat_target_ms": 15000, "research_consent_learners": 192,
            "research_consent_share": 0.64, "consent_withdrawals": 5, "deletion_requests": 3,
            "deletion_median_days": 0.0,
        },
    })
