"""Trang chủ under /v1. Ported from the kickoff demo's Home cases, which were spread over its test files."""
import json

from app.schemas.home import HomeView
from tests.conftest import _issue, correct_key, make_wrong_unit_answer, sse_events, walk_unit


def home(client) -> dict:
    r = client.get("/v1/home")
    assert r.status_code == 200, r.text
    return r.json()


def test_home_before_and_after_a_wrong_answer(learner_api):
    h = home(learner_api)
    assert h["name"] == "Minh" and h["due_cards"] == 0 and h["recent"] == []
    assert h["next_mock"] == {"form_id": "de-thi-thu-1", "title": "Đề thi thử số 1", "n_questions": 10, "minutes": 10,
                              "open_attempt_id": None}
    make_wrong_unit_answer(learner_api)
    h = home(learner_api)
    assert h["due_cards"] == 1 and h["quick_review_count"] == 1
    assert h["recent"] == [{"kind": "unit", "id": "u-dt-01", "title": "Đo lường tần suất bệnh",
                            "subtitle_vi": "Sức khỏe quần thể và dự phòng · chủ đề 1/2", "progress": 0.14}]
    assert "HV-DEMO" not in json.dumps(h)


# ---- Home assertions the demo made inside its exam, card and tutor tests --------------------------

def test_a_running_attempt_is_offered_for_resume(learner_api, clock):
    a = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    clock.advance(seconds=200)
    assert home(learner_api)["next_mock"]["open_attempt_id"] == a["attempt_id"]


def test_a_reviewed_card_is_no_longer_counted(learner_api):
    make_wrong_unit_answer(learner_api)
    cid = learner_api.get("/v1/cards/due").json()["items"][0]["id"]
    learner_api.post(f"/v1/cards/{cid}/reviews", json={"rating": 3})
    assert home(learner_api)["due_cards"] == 0


def test_the_tutors_sessions_are_not_listed_as_recent_chats(learner_api, fake_gw, conn):
    make_wrong_unit_answer(learner_api)
    fake_gw.responses = ['{"insufficient": true}']
    events = sse_events(learner_api.post("/v1/items/q-dt-01/explain").text)
    assert events[-1][0] == "final"
    assert [r["kind"] for r in home(learner_api)["recent"]] == ["unit"]


# ---- added with the port ----------------------------------------------------------------------

def test_home_matches_the_contract_before_anything_happened(learner_api):
    view = HomeView.model_validate(home(learner_api))
    assert view.name == "Minh" and view.due_cards == 0 == view.quick_review_count
    assert view.quick_review_note_vi is None and view.tutor_suggestions == [] and view.recent == []
    assert view.next_mock.form_id == "de-thi-thu-1" and view.next_mock.n_questions == 10 and view.next_mock.minutes == 10


def test_a_visit_is_logged_once_per_half_hour(learner_api, conn, clock, learner):
    from tests.conftest import _issue

    home(learner_api)
    home(learner_api)
    clock.advance(minutes=31)
    learner_api.headers.update(_issue("learner", learner["id"], clock()))      # the access token lasts 30 minutes
    home(learner_api)
    rows = conn.execute("select learner_pid from activity_event where kind = 'visit'").fetchall()
    assert rows == [{"learner_pid": "HV-DEMO-001"}] * 2


def test_an_attempt_left_past_its_deadline_is_closed_when_home_loads(learner_api, conn, clock):
    learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={})
    clock.advance(minutes=11)
    assert home(learner_api)["next_mock"]["open_attempt_id"] is None
    assert conn.execute("select auto_submitted from exam_attempt").fetchone()["auto_submitted"] is True


def test_recent_mixes_units_and_titled_chats_newest_first(learner_api, clock, fake_gw):
    learner_api.get("/v1/units/u-dt-01/next")
    clock.advance(minutes=1)
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    learner_api.post("/v1/chat/sessions", json={})                      # never used: no title, not listed
    learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "Con tôi sốt 39 độ nên uống thuốc gì?"})
    clock.advance(minutes=1)
    learner_api.get("/v1/units/u-dt-02/next")
    recent = home(learner_api)["recent"]
    assert [(r["kind"], r["id"]) for r in recent] == [("unit", "u-dt-02"), ("chat", str(sid)), ("unit", "u-dt-01")]
    assert recent[1]["title"] == "Con tôi sốt 39 độ nên uống thuốc gì?"


def test_another_learner_sees_their_own_home(api, learner_api, tokens_for_new_learner):
    make_wrong_unit_answer(learner_api)
    other = api.get("/v1/home", headers=tokens_for_new_learner()).json()
    assert other["name"] == "Người học khác" and other["due_cards"] == 0 and other["recent"] == []


def test_mock_mode_still_serves_the_example(mock_client):
    assert mock_client.get("/v1/home").status_code == 200


# ---- phase 5A: the quick review, what the rules did, where the learner is -------------------------

def sign_in_again(client, learner, clock) -> None:
    client.headers.update(_issue("learner", learner["id"], clock()))    # access tokens last 30 minutes


def test_nothing_is_suggested_on_the_first_visit(learner_api):
    h = home(learner_api)
    assert h["tutor_suggestions"] == [] and h["quick_review_note_vi"] is None and h["quick_review_count"] == 0


def test_what_the_rules_did_since_the_last_visit_is_listed_once(learner_api, clock, learner, conn):
    home(learner_api)                                                      # visit 1 (builds that day's session)
    clock.advance(minutes=1)
    make_wrong_unit_answer(learner_api)                                    # a card and an example, after visit 1
    clock.advance(days=1)
    sign_in_again(learner_api, learner, clock)
    h = home(learner_api)                                                  # visit 2, a new day: builds today's set
    HomeView.model_validate(h)
    set_id = conn.execute("select id from practice_set").fetchone()["id"]
    assert h["tutor_suggestions"] == [
        {"kind": "cards_created", "text_vi": "Tạo 1 thẻ ôn từ câu bạn trả lời sai",
         "action": {"label_vi": "Xem thẻ", "target": "cards", "id": None}},
        {"kind": "example_added", "text_vi": "Thêm 1 ví dụ vào lộ trình vì câu bạn trả lời sai", "action": None},
        {"kind": "practice_added", "text_vi": "Bổ sung 6 câu luyện cho hôm nay",
         "action": {"label_vi": "Luyện", "target": "practice_set", "id": str(set_id)}}]
    assert h["quick_review_note_vi"] == "1 thẻ mới từ câu bạn trả lời sai"
    assert home(learner_api)["tutor_suggestions"] == h["tutor_suggestions"]    # same visit: the same list
    clock.advance(minutes=45)
    sign_in_again(learner_api, learner, clock)
    later = home(learner_api)                                              # visit 3: all of it is old news
    assert later["tutor_suggestions"] == [] and later["quick_review_note_vi"] is None


def test_quick_review_counts_due_cards_and_unanswered_practice_items(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)
    clock.advance(days=1)
    sign_in_again(learner_api, learner, clock)
    assert home(learner_api)["quick_review_count"] == 1 + 6
    assert home(learner_api)["due_cards"] == 1
    first = learner_api.get("/v1/session/today/practice").json()["items"][0]["question_id"]
    learner_api.post("/v1/session/today/practice/responses", json={"question_id": first, "chosen": correct_key(conn, first)})
    assert home(learner_api)["quick_review_count"] == 1 + 5
    learner_api.post("/v1/session/today/practice/complete")
    assert home(learner_api)["quick_review_count"] == 1


def test_a_finished_practice_set_is_no_longer_suggested(learner_api, conn, clock, learner):
    home(learner_api)
    clock.advance(minutes=1)
    make_wrong_unit_answer(learner_api)
    clock.advance(days=1)
    sign_in_again(learner_api, learner, clock)
    assert "practice_added" in [s["kind"] for s in home(learner_api)["tutor_suggestions"]]     # built by this visit
    learner_api.post("/v1/session/today/practice/complete")
    assert "practice_added" not in [s["kind"] for s in home(learner_api)["tutor_suggestions"]]


def test_opening_home_builds_the_days_session_once(learner_api, conn):
    home(learner_api)
    home(learner_api)
    assert conn.execute("select count(*) c from daily_session").fetchone()["c"] == 1
    assert [s["kind"] for s in learner_api.get("/v1/session/today").json()["steps"]] == ["continue"]


def test_a_recent_unit_shows_where_the_learner_is(learner_api):
    make_wrong_unit_answer(learner_api)                                    # u-dt-01: past the first card, on the quiz
    unit = home(learner_api)["recent"][0]
    assert unit["subtitle_vi"] == "Sức khỏe quần thể và dự phòng · chủ đề 1/2" and unit["progress"] == 0.14     # 1 of 7
    walk_unit(learner_api, "u-dt-01")
    assert home(learner_api)["recent"][0]["progress"] == 1


def test_a_recent_chat_is_labelled(learner_api):
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "Con tôi sốt 39 độ nên uống thuốc gì?"})
    chat = home(learner_api)["recent"][0]
    assert (chat["kind"], chat["subtitle_vi"], chat["progress"]) == ("chat", "Hỏi đáp", None)
