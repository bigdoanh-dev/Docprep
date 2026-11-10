"""Password accounts use the same Phase 1 sessions, consent and lifecycle as activation."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.auth.passwords import verify_password
from app.errors import ApiError
from app.repo import credentials
from app.services.auth import (authenticate, create_password_learner, password_login,
                               reset_learner_password, set_learner_credentials)
from tests.conftest import _test_conn
from tests.test_auth_concurrency import _race

PASSWORD = "PasswordTest2026!"
NEW_PASSWORD = "AnotherPassword2026!"


def provision(conn, learner):
    set_learner_credentials(conn, learner["id"], " Student.One ", PASSWORD)
    conn.commit()


def login(api, username="student.one", password=PASSWORD):
    return api.post("/v1/auth/login", json={"username": username, "password": password})


def test_password_login_keeps_existing_learner_consent_tokens_and_identity_private(api, conn, learner, clock):
    provision(conn, learner)
    row = credentials.by_username(conn, "student.one")
    assert row["password_hash"].startswith("$argon2id$") and verify_password(PASSWORD, row["password_hash"])
    response = login(api, " STUDENT.ONE ")
    assert response.status_code == 200
    pair = response.json()
    assert pair["role"] == "learner" and pair["consent_required"] is True
    headers = {"Authorization": "Bearer " + pair["access_token"]}
    me = api.get("/v1/me", headers=headers)
    assert me.status_code == 200 and me.json()["pseudonym_id"] == learner["pseudonym_id"]
    assert "student.one" not in me.text and "password" not in me.text
    assert api.get("/v1/home", headers=headers).json()["error"]["code"] == "consent_required"
    consent = api.get("/v1/consent/current", headers=headers).json()
    assert api.post("/v1/consent", json={"version": consent["version"], "service": True, "research": False}, headers=headers).status_code == 200
    assert api.get("/v1/home", headers=headers).status_code == 200
    rotated = api.post("/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert rotated.status_code == 200 and rotated.json()["access_token"] != pair["access_token"]
    new_headers = {"Authorization": "Bearer " + rotated.json()["access_token"]}
    assert api.post("/v1/auth/logout", headers=new_headers).status_code == 200
    assert api.get("/v1/me", headers=new_headers).status_code == 401


@pytest.mark.parametrize("case", ["unknown", "wrong", "inactive"])
def test_unknown_wrong_and_inactive_learner_logins_are_identical(api, conn, learner, case):
    provision(conn, learner)
    if case == "inactive":
        conn.execute("update learner set active=false where id=%s", (learner["id"],)); conn.commit()
    r = login(api, "missing.user" if case == "unknown" else "student.one", "bad" if case == "wrong" else PASSWORD)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"
    assert r.json()["error"]["message_vi"] == "Tên đăng nhập hoặc mật khẩu không đúng."


def test_unified_staff_login_preserves_role_and_shares_legacy_rate_bucket(api, conn):
    from app.services.auth import create_staff
    create_staff(conn, "staff@example.org", PASSWORD, "Staff", "admin"); conn.commit()
    pair = login(api, " STAFF@example.org ").json()
    assert pair["role"] == "admin" and pair["refresh_token"] and not pair["consent_required"]
    for n in range(5):
        r = (login(api, "staff@example.org", "bad") if n % 2 else
             api.post("/v1/auth/staff/login", json={"email": "staff@example.org", "password": "bad"}))
        assert r.status_code == 401
    assert login(api, "staff@example.org").status_code == 429


def test_parallel_password_guesses_respect_one_shared_rate_bucket(conn, clock):
    def guess(_):
        try:
            with _test_conn() as c:
                password_login(c, "missing.user", PASSWORD, "10.8.0.1", clock())
        except ApiError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sorted(pool.map(guess, range(6))) == [401, 401, 401, 401, 401, 429]


@pytest.mark.parametrize("username", ["ab", "a@b.example", "bad space", "a" * 65, "học.viên"])
def test_provisioning_refuses_invalid_learner_usernames_without_creating_rows(conn, username):
    with pytest.raises(ValueError):
        create_password_learner(conn, username, PASSWORD, "Student")
    assert conn.execute("select count(*) n from learner").fetchone()["n"] == 0


def test_provisioning_refuses_duplicate_binding_and_short_password(conn, learner):
    with pytest.raises(ValueError): set_learner_credentials(conn, learner["id"], "student.one", "short")
    provision(conn, learner)
    with pytest.raises(ValueError): set_learner_credentials(conn, learner["id"], "student.two", PASSWORD)
    with pytest.raises(ValueError): create_password_learner(conn, "STUDENT.ONE", PASSWORD, "Other")
    assert conn.execute("select count(*) n from learner_credential").fetchone()["n"] == 1


def test_reset_revokes_all_old_sessions_and_only_the_new_password_works(api, conn, learner, clock):
    provision(conn, learner)
    pairs = [login(api).json() for _ in range(2)]
    reset_learner_password(conn, "student.one", NEW_PASSWORD, clock()); conn.commit()
    for pair in pairs:
        assert api.get("/v1/me", headers={"Authorization": "Bearer " + pair["access_token"]}).status_code == 401
        assert api.post("/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    assert login(api).status_code == 401
    assert login(api, password=NEW_PASSWORD).status_code == 200


@pytest.mark.parametrize("first", ["reset", "reset_refresh", "refresh", "login"])
def test_password_reset_serializes_with_refresh_and_login(conn, learner, clock, first):
    provision(conn, learner)
    with _test_conn() as c:
        old = password_login(c, "student.one", PASSWORD, "10.1.0.1", clock())
    from app.services.auth import refresh
    def reset(c): return reset_learner_password(c, "student.one", NEW_PASSWORD, clock())
    def signin(c): return password_login(c, "student.one", PASSWORD, "10.1.0.2", clock())
    def rotate(c): return refresh(c, old["refresh_token"], clock())
    a, b = _race(reset if first.startswith("reset") else (rotate if first == "refresh" else signin),
                 (rotate if first == "reset_refresh" else signin) if first.startswith("reset") else reset)
    if first.startswith("reset"):
        assert isinstance(b, ApiError) and b.status == 401
    else:
        assert isinstance(a, dict) and b is None
        with pytest.raises(ApiError): authenticate(conn, a["access_token"], clock())


@pytest.mark.parametrize("mode", ["erase", "keep_pseudonymous"])
def test_account_deletion_removes_password_identity(api, conn, learner, monkeypatch, mode):
    from app.config import settings
    monkeypatch.setitem(settings()["account_deletion"], "learning_records", mode)
    provision(conn, learner)
    pair = login(api).json()
    response = api.delete("/v1/me", headers={"Authorization": "Bearer " + pair["access_token"]})
    assert response.status_code == 200
    assert credentials.by_username(conn, "student.one") is None
    assert login(api).status_code == 401


def test_seed_alpha_never_overwrites_an_existing_password(conn, learner, clock):
    from seed.alpha import run
    run(conn, with_cohort=False)
    reset_learner_password(conn, "learner.demo", NEW_PASSWORD, clock()); conn.commit()
    before = credentials.by_username(conn, "learner.demo")["password_hash"]
    run(conn, with_cohort=False)
    assert credentials.by_username(conn, "learner.demo")["password_hash"] == before
    assert conn.execute("select count(*) n from learner").fetchone()["n"] == 1


def test_cli_provisions_and_resets_without_printing_passwords(conn, monkeypatch, capsys):
    import app.db
    from app.cli import main
    monkeypatch.setattr(app.db, "connect", lambda: _test_conn())
    monkeypatch.setenv("LEARNER_PASSWORD", PASSWORD)
    main(["create-learner", "--username", "cli.student", "--name", "CLI"])
    assert credentials.by_username(conn, "cli.student") is not None
    monkeypatch.setenv("LEARNER_PASSWORD", NEW_PASSWORD)
    main(["reset-learner-password", "--username", "cli.student"])
    assert verify_password(NEW_PASSWORD, credentials.by_username(conn, "cli.student")["password_hash"])
    output = capsys.readouterr().out
    assert PASSWORD not in output and NEW_PASSWORD not in output


def test_login_payload_limits_do_not_echo_passwords(api):
    secret = "s" * 1025
    response = api.post("/v1/auth/login", json={"username": "student.one", "password": secret})
    assert response.status_code == 422 and secret not in response.text
    assert api.post("/v1/auth/login", json={"username": "student.one", "password": PASSWORD, "role": "admin"}).status_code == 422
