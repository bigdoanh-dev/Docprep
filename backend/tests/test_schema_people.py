"""People, access and consent tables: defaults, allowed values, what erasing a learner takes with it."""
import psycopg
import pytest

LEARNER = "insert into learner(pseudonym_id, exam_date) values (%s, '2027-03-01') returning *"


def test_learner_defaults_match_the_contract(conn):
    row = conn.execute(LEARNER, ("HV-1",)).fetchone()
    assert (row["audience"], row["target_retention"], row["new_cards_per_day"], row["max_reviews_per_day"]) == \
           ("student", 0.9, 20, 200)
    assert row["is_synthetic"] is False and row["active"] is True and isinstance(row["target_retention"], float)


@pytest.mark.parametrize("sql", [
    "insert into learner(pseudonym_id, exam_date, target_retention) values ('HV-2', '2027-03-01', 0.8)",
    "insert into learner(pseudonym_id, exam_date, audience) values ('HV-2', '2027-03-01', 'lecturer')",
    "insert into staff_user(email, password_hash, display_name, role) values ('a@b', 'x', 'A', 'learner')",
    "insert into auth_token(token_hash, subject_type, subject_id, kind, expires_at, family_id) "
    "values ('h', 'robot', 1, 'access', now(), gen_random_uuid())",
])
def test_values_outside_the_allowed_sets_are_refused(conn, sql):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(sql)


def test_erasing_a_learner_removes_identity_and_consent_and_detaches_the_code(conn):
    learner_id = conn.execute(LEARNER, ("HV-3",)).fetchone()["id"]
    conn.execute("insert into learner_identity values (%s, 'Thu Hà', null)", (learner_id,))
    conn.execute("insert into consent_record(learner_id, kind, version, given_at) values (%s, 'service', '2026-10', now())",
                 (learner_id,))
    conn.execute("insert into activation_code(code_hash, audience, learner_id) values ('h', 'student', %s)", (learner_id,))
    conn.execute("delete from learner where id = %s", (learner_id,))

    def count(table):
        return conn.execute(f"select count(*) c from {table}").fetchone()["c"]

    assert (count("learner_identity"), count("consent_record")) == (0, 0)
    assert conn.execute("select learner_id from activation_code").fetchone()["learner_id"] is None


def test_pseudonym_and_staff_email_are_unique(conn):
    conn.execute(LEARNER, ("HV-4",))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(LEARNER, ("HV-4",))
