"""Repeatable local Alpha setup; never changes an existing user's password or history."""
from app.config import require_dev_env
from app.repo.staff import find_by_email
from app.services.auth import create_staff, set_learner_credentials
from app.repo import credentials
from seed import run_seed

LOCAL_STAFF = (
    ("admin@alpha.local", "Quản trị Alpha", "admin"),
    ("viewer@alpha.local", "Báo cáo Alpha", "ministry_viewer"),
)
LOCAL_PASSWORD = "AlphaLocal2026!"


def run(conn, with_cohort: bool = True) -> dict:
    require_dev_env("seed-alpha")
    # run_seed's dev profile upsert intentionally resets focus: do not rerun it over a used profile.
    if not conn.execute("select 1 from learner where pseudonym_id='HV-DEMO-001'").fetchone():
        run_seed(conn)
    for email, name, role in LOCAL_STAFF:
        if not find_by_email(conn, email):
            create_staff(conn, email, LOCAL_PASSWORD, name, role)
    # Bind once to the existing demo learner; never overwrite a changed password or create new history.
    demo = conn.execute("select id,active from learner where pseudonym_id='HV-DEMO-001'").fetchone()
    if demo["active"] and not credentials.by_learner(conn, demo["id"]):
        if credentials.by_username(conn, "learner.demo"):
            raise ValueError("learner.demo already belongs to another learner")
        set_learner_credentials(conn, demo["id"], "learner.demo", LOCAL_PASSWORD)
    conn.commit()
    exists = conn.execute("select 1 from learner where is_synthetic union all "
                          "select 1 from question where is_synthetic limit 1").fetchone()
    if with_cohort and not exists:
        from seed.cohort import run as run_cohort
        return run_cohort(conn, learners=30, weeks=2, seed=42)
    return {"cohort": "already present" if exists else "not requested"}
