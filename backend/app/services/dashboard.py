"""Tổng quan toàn quốc (FR-ADM-15, FR-ADM-16): one AdminOverview from the operational tables. The
figures are made by engine/dashboard.py; nothing here names a learner."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.engine import dashboard as E
from app.repo import dashboard as repo

FILTERS = ("school", "audience", "region")
BLOCKS = ("kpis", "weekly_active", "accuracy_by_module", "question_bank", "ai_safety", "schools", "compliance")
AUDIENCES = [{"value": "student", "label_vi": "Sinh viên"}, {"value": "graduate", "label_vi": "Đã tốt nghiệp"}]
WEEKS_SHOWN = 12
RETURN_AFTER = (1, 4, 8)


def overview(conn, filters: dict, now) -> dict:
    cfg = settings()["dashboard"]
    zone = settings()["local_timezone"]
    minimum = cfg["suppression_min"]
    first = repo.first_activity(conn)
    period = filters.get("period") or E.default_period(now, first, zone)
    start, end = E.month_bounds(period, zone)
    scope = {key: filters.get(key) for key in FILTERS}
    learners = repo.learners(conn, scope, end)
    view = {
        "period": period, "computed_at": now, "sample_data": any(row["is_synthetic"] for row in learners),
        "suppressed": not E.visible(len(learners), minimum), "suppression_min": minimum,
        "selected": {"period": period, **scope},
        "filters": {
            "periods": E.period_options(first, now, zone),
            "schools": [{"value": s["code"], "label_vi": s["name"]}
                        for s in repo.schools(conn, dict.fromkeys(FILTERS), end) if E.visible(s["learners"], minimum)],
            "audiences": AUDIENCES,
            "regions": [{"value": region, "label_vi": region} for region in repo.regions(conn)],
        },
        "alerts": [], **dict.fromkeys(BLOCKS),
    }
    if view["suppressed"]:
        return view

    calendar = _Calendar(period, start, end, zone)
    days, school_of = defaultdict(set), {}
    for row in repo.active_days(conn, scope, calendar.weeks_end, zone):
        days[row["learner_id"]].add(row["day"])
        school_of[row["learner_id"]] = row["school"]
    attempts = repo.mock_attempts(conn, scope, end)
    consented = repo.research_consenting(conn, scope, end)
    ai_safety = _ai_safety(conn, scope, start, end, cfg)
    bank = _question_bank(conn, start, end, cfg)
    schools, alert_schools = _schools(conn, scope, end, calendar, days, school_of, attempts, consented, cfg)
    # Open reports are only known as they stand now, so "open over N days" is counted as of now, or
    # as of the period's end for a past period.
    old_reports = repo.open_reports_before(
        conn, min(end, now) - timedelta(days=cfg["alerts"]["report_open_days"]))
    accounts = repo.accounts(conn, scope, end)
    in_period = [a for a in attempts if a["submitted_at"] >= start]

    view.update({
        "kpis": {
            "active_learners": _active(days, *calendar.days),
            "active_learners_previous": _active(days, *calendar.previous_days),
            "accounts_issued": accounts["issued"], "accounts_activated": accounts["activated"],
            "practice_items": repo.practice_items(conn, scope, start, end),
            "mock_attempts": len(in_period),
            "mock_median": E.score_median(_scores(in_period, consented), minimum),
            "cited_claims_share": ai_safety["cited_claims_share"], "cited_claims_target": cfg["cited_claims_target"],
        },
        "weekly_active": {
            "weeks": [{"week_start": monday, "active_learners": _active(days, monday, monday + timedelta(days=7))}
                      for monday in E.weeks_ending(end, WEEKS_SHOWN, zone)],
            "retention": [E.retention({learner: min(seen) for learner, seen in days.items()}, days, n,
                                      calendar.last_day) for n in RETURN_AFTER],
        },
        "alerts": E.alerts(alert_schools, bank["round2_median_days"], old_reports, cfg["alerts"]),
        "accuracy_by_module": _accuracy(conn, consented, start, end, cfg),
        "question_bank": bank,
        "ai_safety": ai_safety,
        "schools": schools,
        "compliance": _compliance(conn, scope, start, end, len(learners), cfg),
    })
    return _rounded(view)


SHARE_DECIMALS = 3


def _rounded(node):
    """Every fraction to three decimals. An exact share with its learner count gives back the counts
    behind it, and two views would then give a withheld group by subtraction."""
    if isinstance(node, float):
        return round(node, SHARE_DECIMALS)
    if isinstance(node, dict):
        return {key: _rounded(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_rounded(value) for value in node]
    return node


def export(conn, filters: dict, staff_id: int, now) -> dict:
    """The view for the Excel file, with the download written to the audit log."""
    view = overview(conn, filters, now)
    repo.record_export(conn, staff_id, view["selected"], now)
    return view


class _Calendar:
    """The period's local days and weeks."""

    def __init__(self, period: str, start, end, zone: str):
        tz = ZoneInfo(zone)
        self.start = start
        first_day, after = start.astimezone(tz).date(), end.astimezone(tz).date()
        previous_start, _ = E.month_bounds(E.previous_period(period), zone)
        self.days = (first_day, after)
        self.previous_days = (previous_start.astimezone(tz).date(), first_day)
        self.last_day = after - timedelta(days=1)
        first_monday = first_day - timedelta(days=first_day.weekday())
        self.weeks = E.weeks_ending(end, (self.last_day - first_monday).days // 7 + 1, zone)
        # The month's last week runs on to its Sunday: a week is counted whole, or its last point reads as a drop.
        self.weeks_end = datetime.combine(self.weeks[-1] + timedelta(days=7), time.min, tzinfo=tz)


def _active(days: dict, since, until, learners=None) -> int:
    """Learners with a day of activity in [since, until)."""
    return sum(1 for learner, seen in days.items()
               if (learners is None or learner in learners) and any(since <= day < until for day in seen))


def _scores(attempts: list[dict], consented: set[int]) -> dict:
    out = defaultdict(list)
    for a in attempts:
        if a["learner_id"] in consented:
            out[a["learner_id"]].append((a["score"], a["size"]))
    return out


def _changes(attempts: list[dict], consented: set[int]) -> dict:
    out = defaultdict(list)
    for a in attempts:
        if a["learner_id"] in consented:
            out[a["learner_id"]].append((a["submitted_at"], a["score"], a["size"]))
    return out


def _days(values) -> float | None:
    value = E.median([float(v) for v in values if v is not None])
    return None if value is None else round(value, 1)


def _schools(conn, scope, end, calendar, days, school_of, attempts, consented, cfg) -> tuple[dict, list[dict]]:
    minimum = cfg["suppression_min"]
    rows, hidden, for_alerts = [], [], []
    for school in repo.schools(conn, scope, end):
        if not school["learners"] and not school["accounts_issued"]:
            continue
        shown = E.visible(school["learners"], minimum)
        for_alerts.append({**school, "visible": shown})
        if not shown:
            hidden.append({"name": school["name"], "region": school["region"], "learners": school["learners"]})
            continue
        members = {learner for learner, code in school_of.items() if code == school["code"]}
        own = [a for a in attempts if a["school"] == school["code"]]
        own_in_period = [a for a in own if a["submitted_at"] >= calendar.start]
        rate = E.share(school["accounts_activated"], school["accounts_issued"])
        weekly = [_active(days, monday, monday + timedelta(days=7), members) for monday in calendar.weeks]
        rows.append({
            "code": school["code"], "name": school["name"], "region": school["region"],
            "accounts_issued": school["accounts_issued"], "accounts_activated": school["accounts_activated"],
            "activation_low": rate is not None and rate < cfg["low_share"],
            "weekly_active": round(sum(weekly) / len(weekly), 1),
            "mock_attempts": len(own_in_period),
            "mock_median": E.score_median(_scores(own_in_period, consented), minimum),
            "first_to_latest": E.first_to_latest(_changes(own, consented), minimum),
        })
    return {"rows": rows, "hidden": hidden}, for_alerts


def _accuracy(conn, consented: set[int], start, end, cfg) -> dict:
    """Share correct per học phần on consented learners' mock answers; a bar under the minimum is withheld."""
    rows = repo.mock_answers_by_module(conn, sorted(consented), start, end)
    answers, correct, who = defaultdict(int), defaultdict(int), defaultdict(set)
    for row in rows:
        answers[row["module_id"]] += row["answers"]
        correct[row["module_id"]] += row["correct"]
        who[row["module_id"]].add(row["learner_id"])
    items = []
    for module in repo.modules(conn):
        learners = len(who[module["id"]])
        value = E.share(correct[module["id"]], answers[module["id"]]) \
            if E.visible(learners, cfg["suppression_min"]) else None
        items.append({"module_id": module["id"], "short_name": module["short_name"], "share": value,
                      "low": value is not None and value < cfg["low_share"], "learners": learners})
    return {"learners": len({row["learner_id"] for row in rows}), "items": items}


def _question_bank(conn, start, end, cfg) -> dict:
    """The whole bank, whatever the filters. The sample bank counts only where sample learners are."""
    synthetic = repo.any_synthetic_learner(conn)
    statuses = repo.question_statuses(conn, synthetic)
    issues = repo.issues(conn, cfg["min_approved_per_issue"], synthetic)
    agree = repo.rounds_agree(conn, start, end, synthetic)
    received = repo.reports(conn, start, end)
    return {
        "approved": statuses.get("approved", 0), "in_review": sum(statuses.get(s, 0) for s in repo.IN_REVIEW),
        "draft": statuses.get("draft", 0), "rejected": statuses.get("rejected", 0),
        "issues_covered": issues["covered"], "issues_total": issues["total"],
        "min_approved_per_issue": cfg["min_approved_per_issue"],
        "round1_median_days": _days(repo.review_round_days(conn, "in_review_r1", start, end, synthetic)),
        "round2_median_days": _days(repo.review_round_days(conn, "in_review_r2", start, end, synthetic)),
        "round2_target_days": cfg["alerts"]["review_r2_target_days"],
        "rounds_agree_share": E.share(agree["agree"], agree["total"]),
        "reports_received": received["received"], "reports_resolved": received["resolved"],
    }


def _ai_safety(conn, scope, start, end, cfg) -> dict:
    a = repo.answers(conn, scope, start, end)
    reports = repo.answer_reports(conn, scope, start, end)
    return {
        "answers": a["answers"], "model_versions": sorted(a["model_versions"]),
        "corpus_versions": sorted(a["corpus_versions"]),
        "cited_claims_share": E.share(a["claims_kept"], a["claims_checked"]),
        "cited_claims_target": cfg["cited_claims_target"],
        "insufficient_share": E.share(a["insufficient"], a["answers"]),
        "declined_share": E.share(a["declined"], a["answers"]),
        "flagged_share": E.share(a["flagged"], a["answered"]),
        "reports_per_1000": round(reports * 1000 / a["answers"], 1) if a["answers"] else None,
    }


def _compliance(conn, scope, start, end, learners: int, cfg) -> dict:
    deletions = repo.deletions(conn, start, end)
    consented = repo.research_consented_at(conn, scope, end)
    return {
        "chat_p95_ms": E.p95(repo.latencies(conn, scope, start, end)),
        "chat_target_ms": cfg["chat_latency_target_s"] * 1000,
        "research_consent_learners": len(consented),
        "research_consent_share": E.share(len(consented), learners),
        "consent_withdrawals": repo.consent_withdrawals(conn, scope, start, end),
        "deletion_requests": len(deletions),
        "deletion_median_days": _days(d["days"] for d in deletions),
    }
