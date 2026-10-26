"""The ministry dashboard's rules: suppression, medians, retention, alerts and the calendar (FR-ADM-15)."""
from datetime import date, datetime, timedelta, timezone

from app.engine import dashboard as D

ZONE = "Asia/Ho_Chi_Minh"
ALERTS = {"activation_rate_min": 0.6, "review_r2_target_days": 7, "report_open_days": 14}


def test_a_figure_with_nine_learners_is_hidden_and_one_with_ten_is_shown():
    assert D.visible(9, 10) is False
    assert D.visible(10, 10) is True


def test_a_share_of_nothing_is_none():
    assert D.share(0, 0) is None
    assert D.share(3, 4) == 0.75


def test_median_and_p95():
    assert D.median([]) is None
    assert D.median([3, 1, 2]) == 2
    assert D.median([1, 2, 3, 4]) == 2.5
    assert D.p95([]) is None
    assert D.p95(list(range(1, 21))) == 19


def test_the_median_score_is_withheld_under_the_minimum():
    nine = {f"l{i}": [(20, 40)] for i in range(9)}
    assert D.score_median(nine, 10) is None
    ten = {**nine, "l9": [(30, 40)]}
    assert D.score_median(ten, 10) == {"share": 0.5, "form_size": 40, "learners": 10}


def test_the_median_score_names_a_form_size_only_when_every_attempt_has_it():
    mixed = {f"l{i}": [(20, 40)] for i in range(9)} | {"l9": [(15, 30)]}
    result = D.score_median(mixed, 10)
    assert result["form_size"] is None
    assert result["share"] == 0.5
    assert result["learners"] == 10


def test_first_to_latest_ignores_learners_with_one_attempt():
    t = datetime(2026, 9, 1, tzinfo=timezone.utc)
    two = {f"l{i}": [(t + timedelta(days=3), 30, 40), (t, 20, 40)] for i in range(10)}
    one = {f"o{i}": [(t, 10, 40)] for i in range(5)}
    assert D.first_to_latest(two | one, 10) == {"share": 0.25, "form_size": 40, "learners": 10}
    assert D.first_to_latest({k: v for k, v in two.items() if k != "l0"} | one, 10) is None


def test_retention_counts_only_learners_first_seen_long_enough_ago():
    end = date(2026, 9, 30)
    first = {"early": date(2026, 9, 1), "late": date(2026, 9, 20), "gone": date(2026, 9, 2)}
    active = {"early": {date(2026, 9, 1), date(2026, 9, 10)}, "late": {date(2026, 9, 20), date(2026, 9, 28)},
              "gone": {date(2026, 9, 2)}}
    result = D.retention(first, active, 1, end)
    # "late" was first seen 10 days before the end: under the two weeks a one-week return needs.
    assert result == {"weeks": 1, "share": 0.5, "learners": 2}
    assert D.retention(first, active, 8, end) == {"weeks": 8, "share": None, "learners": 0}


def _school(name, issued, activated, visible=True):
    return {"name": name, "accounts_issued": issued, "accounts_activated": activated, "visible": visible}


def test_low_activation_fires_under_the_rate_and_not_at_it():
    assert D.alerts([_school("CSĐT A", 10, 6)], None, 0, ALERTS) == []
    [line] = D.alerts([_school("CSĐT E", 50, 29)], None, 0, ALERTS)
    assert line == {"kind": "low_activation", "title_vi": "CSĐT E: 58% tài khoản đã kích hoạt",
                    "detail_vi": "29/50 · dưới 60%"}


def test_a_hidden_school_raises_no_alert():
    assert D.alerts([_school("CSĐT F", 20, 1, visible=False)], None, 0, ALERTS) == []


def test_slow_review_fires_over_the_target_and_not_at_it():
    assert D.alerts([], 7.0, 0, ALERTS) == []
    [line] = D.alerts([], 9.5, 0, ALERTS)
    assert line == {"kind": "slow_review", "title_vi": "Duyệt vòng 2 mất 9,5 ngày (trung vị)",
                    "detail_vi": "Mục tiêu 7 ngày"}


def test_old_reports_fire_from_one():
    assert D.alerts([], None, 0, ALERTS) == []
    [line] = D.alerts([], None, 3, ALERTS)
    assert line == {"kind": "old_reports", "title_vi": "3 báo lỗi chưa xử lý quá 14 ngày",
                    "detail_vi": "Báo lỗi từ học viên"}


def test_alerts_are_at_most_four_lowest_activation_first():
    schools = [_school(f"S{i}", 100, 50 - i) for i in range(5)]
    lines = D.alerts(schools, 10.0, 2, ALERTS)
    assert len(lines) == 4
    assert [line["kind"] for line in lines] == ["low_activation"] * 4
    assert lines[0]["title_vi"].startswith("S4: 46%")


def test_a_month_runs_from_local_midnight():
    start, end = D.month_bounds("2026-09", ZONE)
    assert start == datetime(2026, 8, 31, 17, tzinfo=timezone.utc)
    assert end == datetime(2026, 9, 30, 17, tzinfo=timezone.utc)
    assert D.month_bounds("2026-12", ZONE)[1] == datetime(2026, 12, 31, 17, tzinfo=timezone.utc)


def test_the_default_period_is_the_last_complete_month_once_it_has_activity():
    now = datetime(2026, 10, 13, 3, tzinfo=timezone.utc)
    assert D.default_period(now, datetime(2026, 7, 1, tzinfo=timezone.utc), ZONE) == "2026-09"
    assert D.default_period(now, datetime(2026, 10, 2, tzinfo=timezone.utc), ZONE) == "2026-10"
    assert D.default_period(now, None, ZONE) == "2026-10"


def test_the_period_options_run_from_the_first_activity_newest_first():
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    options = D.period_options(datetime(2026, 8, 5, tzinfo=timezone.utc), now, ZONE)
    assert options == [{"value": "2026-10", "label_vi": "Tháng 10/2026"},
                       {"value": "2026-09", "label_vi": "Tháng 9/2026"},
                       {"value": "2026-08", "label_vi": "Tháng 8/2026"}]
    assert D.period_options(None, now, ZONE) == [{"value": "2026-10", "label_vi": "Tháng 10/2026"}]


def test_the_weeks_end_with_the_week_holding_the_periods_last_day():
    _, end = D.month_bounds("2026-09", ZONE)
    weeks = D.weeks_ending(end, 3, ZONE)
    # 30/09/2026 is a Wednesday; its week starts on Monday 28/09.
    assert weeks == [date(2026, 9, 14), date(2026, 9, 21), date(2026, 9, 28)]
