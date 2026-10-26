"""Findings of the phase 6B review, each pinned (FR-ADM-15, FR-ADM-16).

The cohort is module-wide (`cohort_api`): a test that changes it puts it back."""
from contextlib import contextmanager
from datetime import datetime, timezone

from tests.conftest import _test_conn

OVERVIEW = "/v1/admin/dashboard/overview"
SEPTEMBER = (datetime(2026, 8, 31, 17, tzinfo=timezone.utc), datetime(2026, 9, 30, 17, tzinfo=timezone.utc))
# A learner with a current research consent given before the period's end and a mock answer in it.
CONSENTED_WITH_ANSWERS = """
    select r.id, r.given_at from consent_record r
    where r.kind = 'research' and r.withdrawn_at is null and r.given_at < %(end)s
      and exists (select 1 from item_response i where i.learner_id = r.learner_id and i.context = 'mock'
                  and i.created_at >= %(start)s and i.created_at < %(end)s)
    order by r.id limit 1"""


def _overview(client, **filters) -> dict:
    r = client.get(OVERVIEW, params={"period": "2026-09", **filters}, headers=client.role_headers["ministry_viewer"])
    assert r.status_code == 200, r.text
    return r.json()


def _one(sql: str, args=None):
    with _test_conn() as c:
        return c.execute(sql, args).fetchone()


def _run(sql: str, args=None) -> None:
    with _test_conn() as c:
        c.execute(sql, args)


@contextmanager
def _one_visible_school():
    """Schools B, C and D of the 20-learner cohort join school A, which then has ten learners or more."""
    with _test_conn() as c:
        moved = c.execute(
            """select l.id, l.organisation_id from learner l join organisation o on o.id = l.organisation_id
               where o.code in ('CSDT-B', 'CSDT-C', 'CSDT-D')""").fetchall()
        c.execute("update learner set organisation_id = (select id from organisation where code = 'CSDT-A') "
                  "where id = any(%s)", ([m["id"] for m in moved],))
    try:
        yield
    finally:
        with _test_conn() as c:
            for m in moved:
                c.execute("update learner set organisation_id = %s where id = %s", (m["organisation_id"], m["id"]))


def test_a_school_with_no_region_does_not_break_the_view_or_the_file(cohort_api):
    _run("insert into organisation(code, name, region, is_synthetic) values ('CSDT-X', 'CSĐT X', null, true)")
    _run("""insert into activation_code(code_hash, organisation_id, audience, issued_at)
            select 'review-fix-x', id, 'student', '2026-09-10T03:00Z' from organisation where code = 'CSDT-X'""")
    try:
        view = _overview(cohort_api)
        assert {"name": "CSĐT X", "region": None, "learners": 0} in view["schools"]["hidden"]
        export = cohort_api.get("/v1/admin/dashboard/export", params={"period": "2026-09"},
                                headers=cohort_api.role_headers["ministry_viewer"])
        assert export.status_code == 200
    finally:
        _run("delete from activation_code where code_hash = 'review-fix-x'")
        _run("delete from organisation where code = 'CSDT-X'")


def test_the_charts_last_week_is_a_whole_week_though_the_month_ends_inside_it(cohort_api):
    """30/09/2026 is a Wednesday: the week of 28/09 runs to Sunday 04/10, local time."""
    whole_week = _one(
        """select count(distinct l.id) n from activity_event e join learner l on l.pseudonym_id = e.learner_pid
           where e.occurred_at >= '2026-09-27T17:00Z' and e.occurred_at < '2026-10-04T17:00Z'""")["n"]
    to_month_end = _one(
        """select count(distinct l.id) n from activity_event e join learner l on l.pseudonym_id = e.learner_pid
           where e.occurred_at >= '2026-09-27T17:00Z' and e.occurred_at < '2026-09-30T17:00Z'""")["n"]
    last = _overview(cohort_api)["weekly_active"]["weeks"][-1]
    assert last["week_start"] == "2026-09-28"
    assert whole_week > to_month_end, "the cohort no longer tells the two apart"
    assert last["active_learners"] == whole_week


def test_a_closed_account_kept_under_its_pseudonym_is_not_counted(cohort_api):
    """account_deletion.learning_records = keep_pseudonymous leaves the learner row, inactive."""
    learner = _one(
        """select l.id from learner l where l.is_synthetic and exists (
               select 1 from activity_event e where e.learner_pid = l.pseudonym_id
                 and e.occurred_at >= %s and e.occurred_at < %s) order by l.id limit 1""", SEPTEMBER)
    before = _overview(cohort_api)["kpis"]["active_learners"]
    _run("update learner set active = false where id = %s", (learner["id"],))
    try:
        assert _overview(cohort_api)["kpis"]["active_learners"] == before - 1
    finally:
        _run("update learner set active = true where id = %s", (learner["id"],))


def test_consent_withdrawn_after_the_period_still_leaves_the_outcome_figures(cohort_api):
    """Withdrawal takes the learner out of every outcome figure, past months included; the month's own
    count of consents, as they stood at its end, keeps them."""
    consent = _one(CONSENTED_WITH_ANSWERS, {"start": SEPTEMBER[0], "end": SEPTEMBER[1]})
    before = _overview(cohort_api)
    _run("update consent_record set withdrawn_at = '2026-10-05T00:00Z' where id = %s", (consent["id"],))
    try:
        after = _overview(cohort_api)
        assert after["accuracy_by_module"]["learners"] == before["accuracy_by_module"]["learners"] - 1
        assert after["compliance"]["research_consent_learners"] == before["compliance"]["research_consent_learners"]
    finally:
        _run("update consent_record set withdrawn_at = null where id = %s", (consent["id"],))


def test_consent_given_after_the_period_does_not_reach_back_into_it(cohort_api):
    consent = _one(CONSENTED_WITH_ANSWERS, {"start": SEPTEMBER[0], "end": SEPTEMBER[1]})
    before = _overview(cohort_api)
    _run("update consent_record set given_at = '2026-10-02T00:00Z' where id = %s", (consent["id"],))
    try:
        after = _overview(cohort_api)
        assert after["accuracy_by_module"]["learners"] == before["accuracy_by_module"]["learners"] - 1
        assert after["compliance"]["research_consent_learners"] == before["compliance"]["research_consent_learners"] - 1
    finally:
        _run("update consent_record set given_at = %s where id = %s", (consent["given_at"], consent["id"]))


def _floats(node):
    if isinstance(node, float):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _floats(value)
    elif isinstance(node, list):
        for value in node:
            yield from _floats(value)


def test_no_share_is_exact_enough_to_subtract_one_view_from_another(cohort_api):
    """An exact fraction with its learner count gives back the counts behind it, and two views then
    give a hidden group by subtraction. Shares leave the server rounded to three decimals."""
    with _one_visible_school():
        values = list(_floats(_overview(cohort_api))) + list(_floats(_overview(cohort_api, school="CSDT-A")))
    assert values
    assert [v for v in values if round(v, 3) != v] == []


def test_a_visible_school_has_a_row_of_its_own_figures(cohort_api):
    with _one_visible_school():
        view = _overview(cohort_api)
        own = _overview(cohort_api, school="CSDT-A")
        mocks = _one(
            """select count(*) n from exam_attempt a join exam_form f on f.id = a.form_id
               join learner l on l.id = a.learner_id join organisation o on o.id = l.organisation_id
               where o.code = 'CSDT-A' and f.kind = 'mock' and a.submitted_at >= %s and a.submitted_at < %s""",
            SEPTEMBER)["n"]
        codes = _one(
            """select count(*) filter (where a.issued_at < %(end)s) issued,
                      count(*) filter (where a.activated_at < %(end)s) activated
               from activation_code a join organisation o on o.id = a.organisation_id where o.code = 'CSDT-A'""",
            {"end": SEPTEMBER[1]})
    [row] = view["schools"]["rows"]
    assert (row["code"], row["name"], row["region"]) == ("CSDT-A", "CSĐT A", "Miền Bắc")
    assert (row["accounts_issued"], row["accounts_activated"]) == (codes["issued"], codes["activated"])
    assert row["mock_attempts"] == mocks and mocks > 0
    assert 0 < row["weekly_active"] <= own["kpis"]["active_learners"]
    assert "CSDT-A" in {option["value"] for option in view["filters"]["schools"]}
    assert "CSĐT A" not in {school["name"] for school in view["schools"]["hidden"]}
    assert own["suppressed"] is False and own["kpis"]["mock_attempts"] == mocks
    assert own["kpis"]["active_learners"] <= view["kpis"]["active_learners"]
    assert "HV-" not in str(view)
