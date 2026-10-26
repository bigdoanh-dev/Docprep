"""The learner's profile and settings, and the export of their own data."""
import pytest

from app.schemas.account import Me, MyData


def test_me_matches_the_contract(api, learner_headers):
    body = api.get("/v1/me", headers=learner_headers).json()
    me = Me.model_validate(body)
    assert me.pseudonym_id == "HV-DEMO-001" and me.display_name == "Minh" and me.focus_module_ids == ["g1"]
    assert me.target_retention == 0.9 and me.new_cards_per_day == 20 and me.organisation is None
    assert me.consent.service_given_at is None


def test_only_the_fields_sent_are_changed(api, learner_headers):
    r = api.patch("/v1/me", headers=learner_headers, json={"new_cards_per_day": 15, "target_retention": 0.95})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["new_cards_per_day"] == 15 and body["target_retention"] == 0.95
    assert body["max_reviews_per_day"] == 200 and body["focus_module_ids"] == ["g1"] and body["display_name"] == "Minh"


def test_the_name_and_the_focus_can_be_changed(api, conn, learner_headers):
    body = api.patch("/v1/me", headers=learner_headers,
                     json={"display_name": "  Thu Hà ", "focus_module_ids": ["g1", "g4"]}).json()
    assert body["display_name"] == "Thu Hà" and body["focus_module_ids"] == ["g1", "g4"]
    assert conn.execute("select display_name from learner_identity").fetchone()["display_name"] == "Thu Hà"


@pytest.mark.parametrize("change,code", [
    ({"focus_module_ids": ["g1", "g99"]}, "unknown_module"),
    ({"focus_module_ids": []}, "unknown_module"),
    ({"exam_date": "2026-10-09"}, "invalid_exam_date"),      # the clock says 10/10/2026
    ({"display_name": "   "}, "invalid_request"),
    ({"new_cards_per_day": 0}, "invalid_request"),
    ({"pseudonym_id": "HV-OTHER"}, "invalid_request"),       # not a field a learner may set
])
def test_invalid_changes_are_refused_and_nothing_is_written(api, learner_headers, change, code):
    before = api.get("/v1/me", headers=learner_headers).json()
    r = api.patch("/v1/me", headers=learner_headers, json={"new_cards_per_day": 33, **change})
    assert r.status_code == 422 and r.json()["error"]["code"] == code
    assert api.get("/v1/me", headers=learner_headers).json() == before


def test_today_is_a_valid_exam_date(api, learner_headers):
    assert api.patch("/v1/me", headers=learner_headers, json={"exam_date": "2026-10-10"}).status_code == 200


def test_an_explicit_null_changes_nothing(api, learner_headers):
    before = api.get("/v1/me", headers=learner_headers).json()
    assert api.patch("/v1/me", headers=learner_headers, json={"exam_date": None, "display_name": None}).json() == before


def test_the_export_holds_the_learners_own_records(api, conn, learner, learner_headers):
    conn.execute("insert into item_response(learner_id, question_id, question_version, context, correct) "
                 "values (%s, 'q-dt-01', 1, 'unit', false)", (learner["id"],))
    session_id = conn.execute("insert into chat_session(learner_pid, title) values (%s, 'Câu hỏi') returning id",
                              (learner["pseudonym_id"],)).fetchone()["id"]
    conn.execute("insert into chat_message(session_id, role, text) values (%s, 'user', 'x')", (session_id,))
    other = conn.execute(
        "insert into learner(pseudonym_id, exam_date) values ('HV-OTHER', '2027-03-01') returning id").fetchone()["id"]
    conn.execute("insert into item_response(learner_id, question_id, question_version, context, correct) "
                 "values (%s, 'q-dt-02', 1, 'unit', true)", (other,))
    conn.execute("insert into chat_session(learner_pid, title) values ('HV-OTHER', 'Của người khác')")
    conn.commit()
    body = api.get("/v1/me/data", headers=learner_headers).json()
    data = MyData.model_validate(body)
    assert [r["question_id"] for r in data.responses] == ["q-dt-01"]
    assert data.chat_sessions == [{"id": session_id, "title": "Câu hỏi", "messages": 1}]
    assert data.attempts == [] and data.cards == [] and data.profile.pseudonym_id == "HV-DEMO-001"
