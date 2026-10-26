"""Tổng quan toàn quốc from the operational tables (FR-ADM-15, FR-ADM-16, FR-LRN-26).

One small cohort per module: 20 learners over two weeks ending 05/10/2026, so September holds its
first ten days. With 20 learners every school is under the minimum of 10, and the nation is not."""
import json
import re
from datetime import datetime, timezone

import pytest

from app.schemas.dashboard import AdminOverview
from tests.conftest import _test_conn

SEPTEMBER_END = datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)
OVERVIEW = "/v1/admin/dashboard/overview"
BLOCKS = ("kpis", "weekly_active", "accuracy_by_module", "question_bank", "ai_safety", "schools", "compliance")
PREDICTION = re.compile(r"dự đoán|xác suất|khả năng đỗ|khả năng đậu|điểm dự kiến|\bđỗ\b|\btrượt\b", re.IGNORECASE)


def test_an_empty_database_is_suppressed_not_an_error(api, staff_headers):
    """The seed only: one real learner, no cohort. Runs first: the cohort below is module-wide."""
    r = api.get(OVERVIEW, headers=staff_headers("ministry_viewer"))
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["suppressed"] is True and view["sample_data"] is False
    assert all(view[block] is None for block in BLOCKS) and view["alerts"] == []
    assert view["filters"]["periods"]


def _overview(client, role="ministry_viewer", **filters) -> dict:
    r = client.get(OVERVIEW, params={"period": "2026-09", **filters}, headers=client.role_headers[role])
    assert r.status_code == 200, r.text
    return r.json()


def test_the_cohorts_month_is_a_valid_overview(cohort_api):
    view = _overview(cohort_api)
    AdminOverview.model_validate(view)
    assert view["suppressed"] is False and view["sample_data"] is True
    assert view["selected"] == {"period": "2026-09", "school": None, "audience": None, "region": None}

    hidden = {school["name"] for school in view["schools"]["hidden"]}
    assert "CSĐT F" in hidden
    assert "CSĐT F" not in {row["name"] for row in view["schools"]["rows"]}
    assert "CSDT-F" not in {option["value"] for option in view["filters"]["schools"]}
    with _test_conn() as c:
        issued = c.execute("select count(*) n from activation_code where issued_at < %s",
                           (SEPTEMBER_END,)).fetchone()["n"]
        issued_f = c.execute(
            """select count(*) n from activation_code a join organisation o on o.id = a.organisation_id
               where o.code = 'CSDT-F' and a.issued_at < %s""", (SEPTEMBER_END,)).fetchone()["n"]
    assert issued_f > 0 and view["kpis"]["accounts_issued"] == issued

    kpis = view["kpis"]
    for name in ("active_learners", "active_learners_previous", "accounts_issued", "accounts_activated",
                 "practice_items", "mock_attempts"):
        assert isinstance(kpis[name], int) and kpis[name] >= 0, name
    assert kpis["active_learners"] > 0
    for value in (kpis["cited_claims_share"], kpis["cited_claims_target"]):
        assert value is None or 0 <= value <= 1


def test_a_filter_under_ten_learners_is_suppressed(cohort_api):
    view = _overview(cohort_api, school="CSDT-F")
    assert view["suppressed"] is True
    assert all(view[block] is None for block in BLOCKS) and view["alerts"] == []
    assert view["filters"]["periods"] and view["filters"]["regions"]
    assert view["selected"]["school"] == "CSDT-F"


def test_a_learner_who_withdrew_research_consent_drops_out_of_the_outcome_figures(cohort_api):
    with _test_conn() as c:
        row = c.execute(
            """select r.id from consent_record r join learner l on l.id = r.learner_id
               where r.kind = 'research' and r.withdrawn_at is null and r.given_at < %s
                 and exists (select 1 from item_response i where i.learner_id = l.id and i.context = 'mock'
                             and i.created_at >= '2026-08-31T17:00Z' and i.created_at < %s)
               order by r.id limit 1""", (SEPTEMBER_END, SEPTEMBER_END)).fetchone()
    assert row is not None
    before = _overview(cohort_api)["accuracy_by_module"]["learners"]
    with _test_conn() as c:
        c.execute("update consent_record set withdrawn_at = '2026-09-25T00:00Z' where id = %s", (row["id"],))
    try:
        assert _overview(cohort_api)["accuracy_by_module"]["learners"] == before - 1
    finally:
        with _test_conn() as c:
            c.execute("update consent_record set withdrawn_at = null where id = %s", (row["id"],))


def test_a_deleted_accounts_activity_is_not_counted(cohort_api):
    before = _overview(cohort_api)["kpis"]["active_learners"]
    with _test_conn() as c:
        c.execute("""insert into activity_event(learner_pid, kind, occurred_at, is_synthetic)
                     values ('HV-GONE-0001', 'visit', '2026-09-25T03:00Z', true)""")
    assert _overview(cohort_api)["kpis"]["active_learners"] == before


@pytest.mark.parametrize("role,status", [("learner", 403), ("reviewer", 403), ("ministry_viewer", 200), ("admin", 200)])
def test_only_the_ministry_and_admins_see_it(cohort_api, role, status):
    r = cohort_api.get(OVERVIEW, params={"period": "2026-09"}, headers=cohort_api.role_headers[role])
    assert r.status_code == status


def test_the_overview_names_no_learner_and_predicts_nothing(cohort_api):
    text = json.dumps(_overview(cohort_api), ensure_ascii=False)
    assert "HV-" not in text
    with _test_conn() as c:
        names = {r["display_name"] for r in c.execute(
            "select display_name from learner_identity union select display_name from activation_code "
            "where display_name is not null")}
    assert names and not any(name in text for name in names)
    assert not PREDICTION.search(text)
