"""Learner sign-in by activation code, rotating refresh tokens, sign-out, the rate limit."""
import pytest

CODE = "DEMO-0001"


def activate(api, code=CODE, **kw):
    return api.post("/v1/auth/activate", json={"code": code}, **kw)


def bearer(pair):
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_the_dev_code_signs_the_dev_learner_in(api, learner):
    r = activate(api)
    assert r.status_code == 200, r.text
    pair = r.json()
    assert pair["role"] == "learner" and pair["expires_in"] == 1800 and pair["consent_required"] is True
    assert pair["access_token"].startswith("at_") and pair["refresh_token"].startswith("rt_")
    assert api.get("/v1/me", headers=bearer(pair)).status_code != 401


@pytest.mark.parametrize("typed", ["demo-0001", "  DEMO-0001  "])
def test_a_code_typed_loosely_still_signs_in(api, learner, typed):
    assert activate(api, typed).status_code == 200


def test_tokens_are_stored_only_as_digests(api, conn, learner):
    pair = activate(api).json()
    stored = [r["token_hash"] for r in conn.execute("select token_hash from auth_token")]
    assert len(stored) == 2 and pair["access_token"] not in stored and pair["refresh_token"] not in stored


def test_a_wrong_code_is_a_401_and_is_counted(api, conn, learner):
    r = activate(api, "DEMO-9999")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    assert conn.execute("select count(*) c from auth_failure where kind = 'activate'").fetchone()["c"] == 1


def test_a_first_use_creates_a_learner_from_the_code(api, conn, learner):
    from app.auth.secrets import hash_code
    org = conn.execute("insert into organisation(code, name) values ('CSDT-A', 'CSĐT A') returning id").fetchone()["id"]
    conn.execute("insert into activation_code(code_hash, organisation_id, audience, display_name) "
                 "values (%s, %s, 'graduate', 'Nguyễn Thu Hà')", (hash_code("NEW-0001"), org))
    conn.commit()
    assert activate(api, "new-0001").status_code == 200
    row = conn.execute(
        """select l.pseudonym_id, l.audience, l.organisation_id, i.display_name, c.activated_at, c.display_name as held
           from activation_code c join learner l on l.id = c.learner_id join learner_identity i on i.learner_id = l.id
           where c.code_hash = %s""", (hash_code("NEW-0001"),)).fetchone()
    assert row["pseudonym_id"].startswith("HV-") and row["audience"] == "graduate" and row["organisation_id"] == org
    assert row["display_name"] == "Nguyễn Thu Hà" and row["activated_at"] is not None and row["held"] is None
    assert activate(api, "NEW-0001").status_code == 200                       # second device, same learner
    assert conn.execute("select count(*) c from learner").fetchone()["c"] == 2


def test_the_limit_refuses_even_the_right_code_until_the_window_passes(api, learner, clock):
    for _ in range(5):
        assert activate(api, "DEMO-9999").status_code == 401
    r = activate(api)
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    clock.advance(minutes=16)
    assert activate(api).status_code == 200


def test_refresh_rotates_the_pair(api, learner):
    old = activate(api).json()
    r = api.post("/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["access_token"] != old["access_token"] and new["refresh_token"] != old["refresh_token"]
    assert api.get("/v1/me", headers=bearer(old)).status_code == 401          # the old access token is dead
    assert api.get("/v1/me", headers=bearer(new)).status_code != 401


def test_a_refresh_token_used_twice_cuts_the_device_off(api, learner):
    old = activate(api).json()
    new = api.post("/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}).json()
    again = api.post("/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert again.status_code == 401 and again.json()["error"]["code"] == "unauthenticated"
    assert api.get("/v1/me", headers=bearer(new)).status_code == 401          # the whole family is revoked
    assert api.post("/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 401


def test_other_devices_are_not_affected(api, learner):
    phone, tablet = activate(api).json(), activate(api).json()
    api.post("/v1/auth/refresh", json={"refresh_token": phone["refresh_token"]})
    api.post("/v1/auth/refresh", json={"refresh_token": phone["refresh_token"]})   # reuse: phone is cut off
    assert api.get("/v1/me", headers=bearer(tablet)).status_code != 401


def test_an_expired_refresh_token_says_so(api, learner, clock):
    pair = activate(api).json()
    clock.advance(days=31)
    r = api.post("/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_expired"


def test_an_access_token_cannot_be_used_to_refresh(api, learner):
    pair = activate(api).json()
    assert api.post("/v1/auth/refresh", json={"refresh_token": pair["access_token"]}).status_code == 401


def test_signing_out_ends_this_device_only(api, learner):
    phone, tablet = activate(api).json(), activate(api).json()
    assert api.post("/v1/auth/logout", headers=bearer(phone)).json() == {"ok": True}
    assert api.get("/v1/me", headers=bearer(phone)).status_code == 401
    assert api.post("/v1/auth/refresh", json={"refresh_token": phone["refresh_token"]}).status_code == 401
    assert api.get("/v1/me", headers=bearer(tablet)).status_code != 401


def test_an_access_token_replaced_by_a_refresh_says_expired_not_signed_out(api, learner):
    """A request already in flight with the old access token should retry with the new one."""
    old = activate(api).json()
    api.post("/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    r = api.get("/v1/me", headers=bearer(old))
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_expired"


def test_an_access_token_of_a_signed_out_device_says_signed_out(api, learner):
    pair = activate(api).json()
    api.post("/v1/auth/logout", headers=bearer(pair))
    r = api.get("/v1/me", headers=bearer(pair))
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
