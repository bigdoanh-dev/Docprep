"""Two requests at the same instant: one activation code, one refresh token."""
import threading
import time
from datetime import datetime, timezone

from app.auth.secrets import hash_code
from app.errors import ApiError
from app.services.auth import activate, authenticate, issue_tokens, refresh
from tests.conftest import _test_conn

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)


def _race(first_call, second_call):
    """Run first_call in an open transaction, start second_call while it is open, then commit the
    first. Returns both outcomes; an exception is returned, not raised."""
    first, second = _test_conn(), _test_conn()
    outcome = {}

    def run_second():
        try:
            outcome["second"] = second_call(second)
            second.commit()
        except Exception as e:   # the outcome under test
            outcome["second"] = e
            second.rollback()

    try:
        outcome["first"] = first_call(first)
        thread = threading.Thread(target=run_second)
        thread.start()
        time.sleep(0.6)          # the second call has started and is waiting, or has run ahead
        first.commit()
        thread.join(15)
        assert not thread.is_alive(), "the second call never finished"
    finally:
        first.close()
        second.close()
    return outcome["first"], outcome["second"]


def test_two_simultaneous_first_uses_of_a_code_make_one_learner(conn, learner):
    conn.execute("insert into activation_code(code_hash, audience, display_name) values (%s, 'student', 'Nguyễn Thu Hà')",
                 (hash_code("NEW-0001"),))
    conn.commit()
    a, b = _race(lambda c: activate(c, "NEW-0001", "10.0.0.1", NOW), lambda c: activate(c, "NEW-0001", "10.0.0.2", NOW))
    assert isinstance(a, dict) and isinstance(b, dict), (a, b)
    assert conn.execute("select count(*) c from learner").fetchone()["c"] == 2          # the dev learner and one new
    assert conn.execute("select count(*) c from learner_identity where display_name = 'Nguyễn Thu Hà'").fetchone()["c"] == 1
    owners = {authenticate(conn, pair["access_token"], NOW).subject_id for pair in (a, b)}
    assert len(owners) == 1                                                             # both devices, one learner


def test_two_concurrent_refreshes_with_one_token_do_not_both_succeed(conn, learner):
    issued = issue_tokens(conn, "learner", learner["id"], NOW)
    conn.commit()
    a, b = _race(lambda c: refresh(c, issued.refresh_token, NOW), lambda c: refresh(c, issued.refresh_token, NOW))
    assert isinstance(a, dict)
    assert isinstance(b, ApiError) and b.code == "unauthenticated", b
    live = conn.execute("select count(*) c from auth_token where family_id = %s and revoked_at is null",
                        (issued.family_id,)).fetchone()["c"]
    assert live == 0             # the token was presented twice: the device is cut off
