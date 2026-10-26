"""Staff sign-in by e-mail and password, and creating staff accounts."""
import pytest

from app.services.auth import create_staff

PASSWORD = "một-mật-khẩu-đủ-dài"


@pytest.fixture
def reviewer(conn, api):
    staff_id = create_staff(conn, "  Tham.Dinh@Example.org ", PASSWORD, "Người thẩm định", "reviewer")
    conn.commit()
    return staff_id


def login(api, email="tham.dinh@example.org", password=PASSWORD):
    return api.post("/v1/auth/staff/login", json={"email": email, "password": password})


def test_a_reviewer_signs_in_and_reaches_the_workbench(api, reviewer):
    r = login(api)
    assert r.status_code == 200, r.text
    pair = r.json()
    assert pair["role"] == "reviewer" and pair["consent_required"] is False
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    assert api.get("/v1/review/queue", headers=headers).status_code not in (401, 403)
    assert api.get("/v1/home", headers=headers).status_code == 403


def test_the_email_is_matched_without_regard_to_case(api, reviewer):
    assert login(api, "THAM.DINH@example.org").status_code == 200


@pytest.mark.parametrize("email,password", [
    ("tham.dinh@example.org", "sai-mat-khau-12345"),
    ("khong.co@example.org", PASSWORD),
])
def test_a_wrong_password_and_an_unknown_email_look_the_same(api, reviewer, email, password):
    r = login(api, email, password)
    assert r.status_code == 401
    assert r.json()["error"] == {"code": "unauthenticated", "message_vi": "Email hoặc mật khẩu không đúng.",
                                 "details": None}


def test_an_inactive_account_cannot_sign_in(api, conn, reviewer):
    conn.execute("update staff_user set active = false")
    conn.commit()
    assert login(api).status_code == 401


def test_the_demo_reviewers_cannot_sign_in(api, learner):
    r = login(api, "demo-reviewer-1@example.invalid", "!")
    assert r.status_code == 401


def test_staff_sign_in_is_rate_limited_separately_from_activation(api, reviewer, learner):
    for _ in range(5):
        login(api, password="sai-mat-khau-12345")
    assert login(api).status_code == 429
    assert api.post("/v1/auth/activate", json={"code": "DEMO-0001"}).status_code == 200


@pytest.mark.parametrize("kwargs,needle", [
    ({"role": "learner"}, "role"),
    ({"password": "ngắn"}, "12"),
])
def test_create_staff_refuses_a_bad_role_and_a_short_password(conn, kwargs, needle):
    args = {"email": "a@example.org", "password": PASSWORD, "display_name": "A", "role": "admin", **kwargs}
    with pytest.raises(ValueError, match=needle):
        create_staff(conn, **args)


def test_the_password_is_stored_hashed(conn, reviewer):
    stored = conn.execute("select password_hash from staff_user where email = 'tham.dinh@example.org'").fetchone()
    assert stored["password_hash"].startswith("$argon2") and PASSWORD not in stored["password_hash"]


def test_the_command_creates_an_account(conn, monkeypatch):
    import app.cli as cli
    from tests.conftest import test_database_url
    monkeypatch.setenv("DATABASE_URL", test_database_url())      # the command connects to DATABASE_URL
    monkeypatch.setenv("STAFF_PASSWORD", PASSWORD)
    cli.main(["create-staff", "--email", "quan.tri@example.org", "--name", "Quản trị", "--role", "admin"])
    row = conn.execute("select role, display_name from staff_user where email = 'quan.tri@example.org'").fetchone()
    assert row == {"role": "admin", "display_name": "Quản trị"}
