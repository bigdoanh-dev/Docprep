"""Development data: the two demo reviewers behind the seed's approvals, and one learner to work with."""
from app.config import settings

DEMO_REVIEWERS = [("demo-reviewer-1@example.invalid", "Người thẩm định 1"),
                  ("demo-reviewer-2@example.invalid", "Người thẩm định 2")]
# Not a hash of anything: no password can ever match it, so these accounts cannot sign in.
NO_PASSWORD = "!"


def ensure_demo_reviewers(conn) -> tuple[int, int]:
    ids = [conn.execute(
        """insert into staff_user(email, password_hash, display_name, role, is_demo) values (%s, %s, %s, 'reviewer', true)
           on conflict (email) do update set display_name = excluded.display_name returning id""",
        (email, NO_PASSWORD, name)).fetchone()["id"] for email, name in DEMO_REVIEWERS]
    return ids[0], ids[1]


def ensure_dev_learner(conn) -> dict:
    cfg = settings()
    lc = cfg["learner"]
    learner = conn.execute(
        """insert into learner(pseudonym_id, focus_module_ids, exam_date, target_retention) values (%s, %s, %s, %s)
           on conflict (pseudonym_id) do update set focus_module_ids = excluded.focus_module_ids,
             exam_date = excluded.exam_date returning *""",
        (lc["pseudonym"], lc["focus_module_ids"], cfg["exam_date"],
         cfg.get("fsrs", {}).get("desired_retention", 0.9))).fetchone()
    conn.execute(
        """insert into learner_identity(learner_id, display_name) values (%s, %s)
           on conflict (learner_id) do update set display_name = excluded.display_name""",
        (learner["id"], lc["display_name"]))
    return learner


def ensure_dev_activation_code(conn, learner: dict) -> None:
    """The code in config signs the dev learner in. It is linked and marked activated, so using it
    does not create a second learner."""
    from app.auth.secrets import hash_code

    code = settings()["learner"]["activation_code"]
    conn.execute(
        """insert into activation_code(code_hash, audience, activated_at, learner_id) values (%s, %s, now(), %s)
           on conflict (code_hash) do update set learner_id = excluded.learner_id,
             activated_at = coalesce(activation_code.activated_at, excluded.activated_at)""",
        (hash_code(code), learner["audience"], learner["id"]))
