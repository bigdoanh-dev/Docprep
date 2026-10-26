"""The ministry dashboard's reads (FR-ADM-15). Rows and counts only: the figures are made in
engine/dashboard.py. A learner-facing query takes the filter scope {school, audience, region}; a
deleted account's leftovers (activity, chats, reports keyed by a pseudonym no learner has) never
join a learner, and an account closed but kept under its pseudonym is inactive, so neither counts."""

from psycopg.types.json import Jsonb

# The forms a mock-exam score comes from, as the learner's own progress reads them.
MOCK_KINDS = ("mock", "demo_short", "assembled")
IN_REVIEW = ("prescreen", "in_review_r1", "in_review_r2", "needs_revision")

_SCOPE = """(%(school)s::text is null or o.code = %(school)s)
    and (%(audience)s::text is null or {who}.audience = %(audience)s)
    and (%(region)s::text is null or o.region = %(region)s)"""
_LEARNER_SCOPE = "l.active and " + _SCOPE.format(who="l")
_CODE_SCOPE = _SCOPE.format(who="a")


def _p(scope: dict, **more) -> dict:
    return {"school": scope.get("school"), "audience": scope.get("audience"), "region": scope.get("region"), **more}


def first_activity(conn):
    """When the first counted activity happened, for the period list."""
    return conn.execute(
        """select min(e.occurred_at) as at from activity_event e
           join learner l on l.pseudonym_id = e.learner_pid and l.active""").fetchone()["at"]


def any_synthetic_learner(conn) -> bool:
    return conn.execute("select exists (select 1 from learner where is_synthetic) as x").fetchone()["x"]


def regions(conn) -> list[str]:
    return [r["region"] for r in conn.execute(
        "select distinct region from organisation where region is not null order by region")]


def schools(conn, scope: dict, end) -> list[dict]:
    """Each school the school and region filters keep: its learners (in the audience) and the codes it
    issued and saw activated by the end."""
    return conn.execute(
        f"""select o.code, o.name, o.region,
                   (select count(*) from learner l where l.organisation_id = o.id and l.active and l.created_at < %(end)s
                      and (%(audience)s::text is null or l.audience = %(audience)s)) as learners,
                   (select count(*) from activation_code a where a.organisation_id = o.id and a.issued_at < %(end)s
                      and (%(audience)s::text is null or a.audience = %(audience)s)) as accounts_issued,
                   (select count(*) from activation_code a where a.organisation_id = o.id and a.activated_at < %(end)s
                      and (%(audience)s::text is null or a.audience = %(audience)s)) as accounts_activated
            from organisation o
            where (%(school)s::text is null or o.code = %(school)s) and (%(region)s::text is null or o.region = %(region)s)
            order by o.name""", _p(scope, end=end)).fetchall()


def accounts(conn, scope: dict, end) -> dict:
    """Codes issued and activated by the end, in scope; codes of no school count only with no school filter."""
    return conn.execute(
        f"""select count(*) filter (where a.issued_at < %(end)s) as issued,
                   count(*) filter (where a.activated_at < %(end)s) as activated
            from activation_code a left join organisation o on o.id = a.organisation_id
            where {_CODE_SCOPE}""", _p(scope, end=end)).fetchone()


def learners(conn, scope: dict, end) -> list[dict]:
    """The learners in scope whose account existed by the end."""
    return conn.execute(
        f"""select l.id, o.code as school, l.is_synthetic from learner l
            left join organisation o on o.id = l.organisation_id
            where l.created_at < %(end)s and {_LEARNER_SCOPE}""", _p(scope, end=end)).fetchall()


def active_days(conn, scope: dict, end, zone: str) -> list[dict]:
    """Each learner's days with activity before `end`, in local time."""
    return conn.execute(
        f"""select distinct l.id as learner_id, o.code as school, (e.occurred_at at time zone %(zone)s)::date as day
            from activity_event e join learner l on l.pseudonym_id = e.learner_pid
            left join organisation o on o.id = l.organisation_id
            where e.occurred_at < %(end)s and {_LEARNER_SCOPE}""", _p(scope, end=end, zone=zone)).fetchall()


def practice_items(conn, scope: dict, start, end) -> int:
    return conn.execute(
        f"""select count(*) n from activity_event e join learner l on l.pseudonym_id = e.learner_pid
            left join organisation o on o.id = l.organisation_id
            where e.kind in ('unit_response', 'practice_response') and e.occurred_at >= %(start)s
              and e.occurred_at < %(end)s and {_LEARNER_SCOPE}""", _p(scope, start=start, end=end)).fetchone()["n"]


def _research(conn, scope: dict, end, still: str) -> set[int]:
    return {r["id"] for r in conn.execute(
        f"""select distinct l.id from consent_record r join learner l on l.id = r.learner_id
            left join organisation o on o.id = l.organisation_id
            where r.kind = 'research' and r.given_at < %(end)s and {still} and {_LEARNER_SCOPE}""",
        _p(scope, end=end))}


def research_consenting(conn, scope: dict, end) -> set[int]:
    """Learners whose data an outcome figure of the period may use: research consent given before its
    end and not withdrawn since. A withdrawal takes a learner out of past periods too."""
    return _research(conn, scope, end, "r.withdrawn_at is null")


def research_consented_at(conn, scope: dict, end) -> set[int]:
    """Learners whose research consent stood at the end of the period: the count of consents, as a fact of then."""
    return _research(conn, scope, end, "(r.withdrawn_at is null or r.withdrawn_at >= %(end)s)")


def consent_withdrawals(conn, scope: dict, start, end) -> int:
    return conn.execute(
        f"""select count(*) n from consent_record r join learner l on l.id = r.learner_id
            left join organisation o on o.id = l.organisation_id
            where r.kind = 'research' and r.withdrawn_at >= %(start)s and r.withdrawn_at < %(end)s
              and {_LEARNER_SCOPE}""", _p(scope, start=start, end=end)).fetchone()["n"]


def mock_attempts(conn, scope: dict, end) -> list[dict]:
    """Every mock attempt handed in before the end, with its score and size."""
    return conn.execute(
        f"""select l.id as learner_id, o.code as school, a.submitted_at, a.score,
                   cardinality(a.question_order) as size
            from exam_attempt a join exam_form f on f.id = a.form_id
            join learner l on l.id = a.learner_id left join organisation o on o.id = l.organisation_id
            where a.submitted_at is not null and a.submitted_at < %(end)s and f.kind = any(%(kinds)s)
              and cardinality(a.question_order) > 0 and {_LEARNER_SCOPE}""",
        _p(scope, end=end, kinds=list(MOCK_KINDS))).fetchall()


def modules(conn) -> list[dict]:
    return conn.execute(
        "select id, short_name from module where core_issue_group_id is not null order by ord").fetchall()


def mock_answers_by_module(conn, learner_ids: list[int], start, end) -> list[dict]:
    """Mock-exam answers in the window by those learners, per học phần and learner. An answer to a
    question with no core issue belongs to no học phần and is left out."""
    return conn.execute(
        """select m.id as module_id, i.learner_id, count(*) as answers, count(*) filter (where i.correct) as correct
           from item_response i
           join question q on q.id = i.question_id and q.version = i.question_version
           join core_issue c on c.id = q.core_issue_id
           join module m on m.core_issue_group_id = c.group_id
           where i.context = 'mock' and i.learner_id = any(%s) and i.created_at >= %s and i.created_at < %s
           group by m.id, i.learner_id""", (learner_ids, start, end)).fetchall()


# The question bank: the whole bank, no learner filter. The sample bank counts only where sample learners are.

def question_statuses(conn, synthetic: bool) -> dict[str, int]:
    """The latest version of each question, by status."""
    return {r["status"]: r["n"] for r in conn.execute(
        """select status, count(*) n from (
               select distinct on (id) status from question where (not is_synthetic or %s) order by id, version desc
           ) latest group by status""", (synthetic,))}


def issues(conn, minimum: int, synthetic: bool) -> dict:
    return conn.execute(
        """select (select count(*) from core_issue) as total,
                  (select count(*) from (select core_issue_id from question
                                         where status = 'approved' and core_issue_id is not null and (not is_synthetic or %s)
                                         group by core_issue_id having count(*) >= %s) covered) as covered""",
        (synthetic, minimum)).fetchone()


_NOT_SAMPLE = """(%(synthetic)s or not exists (select 1 from question q where t.target_type = 'question'
                                                 and q.id = t.target_id and q.is_synthetic))"""


def review_round_days(conn, round_status: str, start, end, synthetic: bool) -> list[float]:
    """For each decision taken in the window that moved an item out of that round, the days since it entered it."""
    return [r["days"] for r in conn.execute(
        f"""select extract(epoch from t.at - entered.at) / 86400 as days
            from status_transition t
            join lateral (select e.at from status_transition e
                          where e.target_type = t.target_type and e.target_id = t.target_id and e.version = t.version
                            and e.to_status = %(round)s and e.at <= t.at order by e.at desc limit 1) entered on true
            where t.from_status = %(round)s and t.at >= %(start)s and t.at < %(end)s and {_NOT_SAMPLE}""",
        {"round": round_status, "start": start, "end": end, "synthetic": synthetic})]


def rounds_agree(conn, start, end, synthetic: bool) -> dict:
    """Round-2 decisions in the window, and how many repeat the round-1 decision before them."""
    return conn.execute(
        f"""select count(*) as total, count(*) filter (where first.decision = t.decision) as agree
            from review_decision t
            join lateral (select d.decision from review_decision d
                          where d.target_type = t.target_type and d.target_id = t.target_id and d.version = t.version
                            and d.round = 1 and d.created_at <= t.created_at order by d.created_at desc limit 1) first on true
            where t.round = 2 and t.created_at >= %(start)s and t.created_at < %(end)s and {_NOT_SAMPLE}""",
        {"start": start, "end": end, "synthetic": synthetic}).fetchone()


def reports(conn, start, end) -> dict:
    """Error reports from learners created in the window, and how many of those are resolved."""
    return conn.execute(
        """select count(*) as received, count(*) filter (where status = 'resolved') as resolved
           from error_report where created_at >= %s and created_at < %s""", (start, end)).fetchone()


def open_reports_before(conn, before) -> int:
    return conn.execute("select count(*) n from error_report where status = 'open' and created_at < %s",
                        (before,)).fetchone()["n"]


# Chat answers and their reports, by the learner who asked.

_ASKED = """from chat_message m join chat_session s on s.id = m.session_id
            join learner l on l.pseudonym_id = s.learner_pid left join organisation o on o.id = l.organisation_id
            where m.role = 'assistant' and m.created_at >= %(start)s and m.created_at < %(end)s"""


def answers(conn, scope: dict, start, end) -> dict:
    return conn.execute(
        f"""select count(*) as answers,
                   coalesce(array_agg(distinct m.model_version) filter (where m.model_version is not null), '{{}}') as model_versions,
                   coalesce(array_agg(distinct m.corpus_version) filter (where m.corpus_version is not null), '{{}}') as corpus_versions,
                   coalesce(sum(m.claims_checked) filter (where m.claims_checked > 0), 0) as claims_checked,
                   coalesce(sum(m.claims_checked - coalesce(m.claims_removed, 0)) filter (where m.claims_checked > 0), 0) as claims_kept,
                   count(*) filter (where m.state = 'insufficient_evidence') as insufficient,
                   count(*) filter (where m.state = 'declined') as declined,
                   count(*) filter (where m.state = 'answered') as answered,
                   count(*) filter (where m.state = 'answered' and m.claims_removed > 0) as flagged
            {_ASKED} and {_LEARNER_SCOPE}""", _p(scope, start=start, end=end)).fetchone()


def latencies(conn, scope: dict, start, end) -> list[int]:
    return [r["latency_ms"] for r in conn.execute(
        f"select m.latency_ms {_ASKED} and m.latency_ms is not null and {_LEARNER_SCOPE}",
        _p(scope, start=start, end=end))]


def answer_reports(conn, scope: dict, start, end) -> int:
    return conn.execute(
        f"""select count(*) n from error_report r join learner l on l.pseudonym_id = r.learner_pid
            left join organisation o on o.id = l.organisation_id
            where r.target_type = 'answer' and r.created_at >= %(start)s and r.created_at < %(end)s
              and {_LEARNER_SCOPE}""", _p(scope, start=start, end=end)).fetchone()["n"]


def deletions(conn, start, end) -> list[dict]:
    """Deletion requests made in the window. The account is gone, so no filter can place them."""
    return conn.execute(
        """select extract(epoch from completed_at - requested_at) / 86400 as days from deletion_request
           where requested_at >= %s and requested_at < %s""", (start, end)).fetchall()


def record_export(conn, staff_id: int, filters: dict, now) -> None:
    """Who downloaded which view, and when (FR-ADM-16)."""
    conn.execute(
        """insert into audit_log(actor_type, actor_id, action, target, at, details)
           values ('staff', %s, 'dashboard_export', 'admin_overview', %s, %s)""",
        (str(staff_id), now, Jsonb(filters)))
