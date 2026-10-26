"""Consent: the text, giving it, withdrawing it, and what the gate does with each."""


def give(api, headers, **body):
    return api.post("/v1/consent", headers=headers, json={"version": "2026-10", "service": True, **body})


def let_in(response) -> bool:
    return response.status_code not in (401, 403)


def test_the_current_text_is_served(api, learner_headers):
    body = api.get("/v1/consent/current", headers=learner_headers).json()
    assert body["version"] == "2026-10" and body["service_text_vi"] and body["research_text_vi"]


def test_giving_service_consent_opens_the_app(api, learner_headers):
    assert api.get("/v1/home", headers=learner_headers).status_code == 403
    r = give(api, learner_headers)
    assert r.status_code == 200, r.text
    status = r.json()
    assert status["version"] == "2026-10" and status["service_given_at"] and status["research_given_at"] is None
    assert let_in(api.get("/v1/home", headers=learner_headers))


def test_research_consent_is_optional_and_separate(api, conn, learner_headers):
    assert give(api, learner_headers, research=True).json()["research_given_at"]
    after = api.request("DELETE", "/v1/consent", headers=learner_headers).json()       # default kind: research
    assert after["research_given_at"] is None and after["service_given_at"]
    assert let_in(api.get("/v1/home", headers=learner_headers))                        # still open
    kinds = conn.execute("select kind, withdrawn_at is not null as withdrawn from consent_record order by id").fetchall()
    assert kinds == [{"kind": "service", "withdrawn": False}, {"kind": "research", "withdrawn": True}]


def test_withdrawing_service_consent_closes_the_app_again(api, learner_headers):
    give(api, learner_headers)
    after = api.request("DELETE", "/v1/consent", params={"kind": "service"}, headers=learner_headers).json()
    assert after["service_given_at"] is None and after["version"] is None
    assert api.get("/v1/home", headers=learner_headers).json()["error"]["code"] == "consent_required"
    assert let_in(api.get("/v1/me", headers=learner_headers))                          # the account stays reachable


def test_service_consent_cannot_be_declined(api, learner_headers):
    r = give(api, learner_headers, service=False)
    assert r.status_code == 422 and r.json()["error"]["code"] == "service_consent_required"


def test_an_outdated_version_is_refused(api, learner_headers):
    r = api.post("/v1/consent", headers=learner_headers, json={"version": "2025-01", "service": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "consent_version_outdated"


def test_giving_consent_twice_keeps_one_record(api, conn, learner_headers):
    first = give(api, learner_headers).json()
    assert give(api, learner_headers).json() == first
    assert conn.execute("select count(*) c from consent_record").fetchone()["c"] == 1


def test_research_consent_can_be_dropped_by_giving_consent_again_without_it(api, learner_headers):
    assert give(api, learner_headers, research=True).json()["research_given_at"]
    assert give(api, learner_headers, research=False).json()["research_given_at"] is None


def test_a_new_consent_version_closes_the_gate(api, learner_headers, monkeypatch):
    from app.config import settings
    give(api, learner_headers)
    monkeypatch.setitem(settings()["consent"], "version", "2027-01")
    assert api.get("/v1/home", headers=learner_headers).json()["error"]["code"] == "consent_required"


def test_sign_in_reports_whether_consent_is_needed(api, learner, learner_headers):
    assert api.post("/v1/auth/activate", json={"code": "DEMO-0001"}).json()["consent_required"] is True
    give(api, learner_headers)
    assert api.post("/v1/auth/activate", json={"code": "DEMO-0001"}).json()["consent_required"] is False


def test_research_consent_follows_the_consent_version(api, conn, learner_headers, monkeypatch):
    """Consent given to an older text does not count as consent to the new one."""
    from app.config import settings
    give(api, learner_headers, research=True)
    monkeypatch.setitem(settings()["consent"], "version", "2027-01")
    r = api.post("/v1/consent", headers=learner_headers, json={"version": "2027-01", "service": True, "research": True})
    assert r.status_code == 200 and r.json()["research_given_at"]
    active = conn.execute("select kind, version from consent_record where withdrawn_at is null order by kind").fetchall()
    assert active == [{"kind": "research", "version": "2027-01"}, {"kind": "service", "version": "2027-01"}]
