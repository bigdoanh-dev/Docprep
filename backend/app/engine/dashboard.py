"""The ministry dashboard's rules (FR-ADM-15): suppression, medians, retention, the alert rules and the
calendar a period is cut on. Pure: the figures come in as counts and value lists, nothing reads the clock."""
from datetime import date, datetime, timedelta, timezone
from statistics import median as _median
from zoneinfo import ZoneInfo


# The calendar: a period is a month in local time; a week starts on Monday, local.

def month_bounds(period: str, zone: str) -> tuple[datetime, datetime]:
    """The month `YYYY-MM` as a UTC window: start inclusive, end exclusive."""
    year, month = (int(part) for part in period.split("-"))
    tz = ZoneInfo(zone)
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _month_of(moment: datetime, zone: str) -> tuple[int, int]:
    local = moment.astimezone(ZoneInfo(zone))
    return local.year, local.month


def _period(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _previous(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def previous_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    return _period(*_previous(year, month))


def default_period(now: datetime, first_activity: datetime | None, zone: str) -> str:
    """The last complete month; the current one when nothing happened before it."""
    current = _month_of(now, zone)
    if first_activity is None or _month_of(first_activity, zone) >= current:
        return _period(*current)
    return _period(*_previous(*current))


def period_options(first_activity: datetime | None, now: datetime, zone: str) -> list[dict]:
    """Every month from the first activity to the current one, newest first."""
    month = _month_of(now, zone)
    first = _month_of(first_activity, zone) if first_activity is not None else month
    options = []
    while True:
        options.append({"value": _period(*month), "label_vi": f"Tháng {month[1]}/{month[0]}"})
        if month <= first:
            return options
        month = _previous(*month)


def weeks_ending(period_end: datetime, n: int, zone: str) -> list[date]:
    """The Mondays of the `n` weeks ending with the week that holds the period's last day."""
    last_day = (period_end - timedelta(microseconds=1)).astimezone(ZoneInfo(zone)).date()
    last_monday = last_day - timedelta(days=last_day.weekday())
    return [last_monday - timedelta(weeks=k) for k in range(n - 1, -1, -1)]


# Suppression and the arithmetic.

def visible(learners: int, minimum: int) -> bool:
    """A figure resting on fewer than `minimum` learners is withheld."""
    return learners >= minimum


def share(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def median(values: list[float]) -> float | None:
    return _median(values) if values else None


def p95(values: list[int]) -> int | None:
    """The nearest-rank 95th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    rank = -(-95 * len(ordered) // 100)
    return ordered[rank - 1]


def _common_size(sizes: list[int]) -> int | None:
    return sizes[0] if sizes and all(size == sizes[0] for size in sizes) else None


def score_median(per_learner: dict[str, list[tuple[int, int]]], minimum: int) -> dict | None:
    """The median of every mock attempt's score ÷ size, over consented learners' attempts in the period."""
    attempts = [attempt for learner in per_learner.values() for attempt in learner]
    learners = sum(1 for learner in per_learner.values() if learner)
    if not visible(learners, minimum):
        return None
    return {"share": median([score / size for score, size in attempts]),
            "form_size": _common_size([size for _, size in attempts]), "learners": learners}


def first_to_latest(per_learner: dict[str, list[tuple[datetime, int, int]]], minimum: int) -> dict | None:
    """The median change from a learner's first mock to their latest, among learners with two or more."""
    changes, sizes = [], []
    for attempts in per_learner.values():
        if len(attempts) < 2:
            continue
        ordered = sorted(attempts)
        (_, first_score, first_size), (_, last_score, last_size) = ordered[0], ordered[-1]
        changes.append(last_score / last_size - first_score / first_size)
        sizes += [first_size, last_size]
    if not visible(len(changes), minimum):
        return None
    return {"share": median(changes), "form_size": _common_size(sizes), "learners": len(changes)}


def retention(first_seen: dict[str, date], active_days: dict[str, set[date]], weeks: int,
              period_end: date) -> dict:
    """Of learners first active at least `weeks` + 1 weeks before the period's last day, the share active
    in the 7 days that start `weeks` weeks after their first activity."""
    cutoff = period_end - timedelta(weeks=weeks + 1)
    eligible = [learner for learner, first in first_seen.items() if first <= cutoff]
    returned = 0
    for learner in eligible:
        start = first_seen[learner] + timedelta(weeks=weeks)
        if any(start <= day < start + timedelta(days=7) for day in active_days.get(learner, ())):
            returned += 1
    return {"weeks": weeks, "share": share(returned, len(eligible)), "learners": len(eligible)}


# The alert rules. Each line is a template filled with the numbers that triggered it.

MAX_ALERTS = 4


def percent(value: float) -> str:
    return f"{round(value * 100)}%"


def days(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def alerts(schools: list[dict], round2_median_days: float | None, old_reports: int, cfg: dict) -> list[dict]:
    """low_activation per visible school (lowest rate first), then slow_review, then old_reports; at most 4."""
    threshold = cfg["activation_rate_min"]
    low = []
    for school in schools:
        rate = share(school["accounts_activated"], school["accounts_issued"])
        if school["visible"] and rate is not None and rate < threshold:
            low.append((rate, school))
    lines = [{"kind": "low_activation",
              "title_vi": f"{school['name']}: {percent(rate)} tài khoản đã kích hoạt",
              "detail_vi": f"{school['accounts_activated']}/{school['accounts_issued']} · dưới {percent(threshold)}"}
             for rate, school in sorted(low, key=lambda pair: pair[0])]
    target = cfg["review_r2_target_days"]
    if round2_median_days is not None and round2_median_days > target:
        lines.append({"kind": "slow_review", "title_vi": f"Duyệt vòng 2 mất {days(round2_median_days)} ngày (trung vị)",
                      "detail_vi": f"Mục tiêu {target} ngày"})
    if old_reports > 0:
        lines.append({"kind": "old_reports",
                      "title_vi": f"{old_reports} báo lỗi chưa xử lý quá {cfg['report_open_days']} ngày",
                      "detail_vi": "Báo lỗi từ học viên"})
    return lines[:MAX_ALERTS]
