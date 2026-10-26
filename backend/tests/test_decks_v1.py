"""Bộ thẻ: decks by học phần, and suspending a card."""
from tests.conftest import make_wrong_unit_answer


def decks(client) -> list[dict]:
    r = client.get("/v1/decks")
    assert r.status_code == 200, r.text
    return r.json()["items"]


def the_card(client) -> dict:
    return client.get("/v1/cards/due").json()["items"][0]


def test_no_cards_no_decks(learner_api):
    assert learner_api.get("/v1/decks").json() == {"items": []}


def test_a_deck_counts_new_learning_and_due(learner_api):
    make_wrong_unit_answer(learner_api)
    assert decks(learner_api) == [{
        "module_id": "g1", "name": "Vấn đề sức khỏe quần thể cần can thiệp ở cấp ban đầu để ngăn ngừa tiến triển",
        "short_name": "Sức khỏe quần thể và dự phòng", "new": 1, "learning": 0, "due": 1}]
    learner_api.post(f"/v1/cards/{the_card(learner_api)['id']}/reviews", json={"rating": 3})
    deck = decks(learner_api)[0]
    assert (deck["new"], deck["learning"], deck["due"]) == (0, 1, 0)


def test_a_suspended_card_leaves_every_queue_and_comes_back_unchanged(learner_api, conn):
    make_wrong_unit_answer(learner_api)
    card_id = the_card(learner_api)["id"]
    due_at = conn.execute("select due_at from card").fetchone()["due_at"]
    r = learner_api.patch(f"/v1/cards/{card_id}", json={"suspended": True})
    assert r.status_code == 200 and r.json() == {"id": card_id, "suspended": True}
    assert learner_api.get("/v1/cards/due").json() == {"items": [], "total_due": 0}
    assert learner_api.get("/v1/home").json()["due_cards"] == 0 and decks(learner_api) == []
    assert learner_api.patch(f"/v1/cards/{card_id}", json={"suspended": True}).status_code == 200      # again: no error
    assert learner_api.patch(f"/v1/cards/{card_id}", json={"suspended": False}).json() == {"id": card_id, "suspended": False}
    assert the_card(learner_api)["id"] == card_id and learner_api.get("/v1/home").json()["due_cards"] == 1
    assert conn.execute("select due_at from card").fetchone()["due_at"] == due_at
    conn.rollback()


def test_another_learners_card_is_not_found_and_stays_as_it_was(api, learner_api, conn, tokens_for_new_learner):
    make_wrong_unit_answer(learner_api)
    card_id = the_card(learner_api)["id"]
    other = tokens_for_new_learner()
    r = api.patch(f"/v1/cards/{card_id}", json={"suspended": True}, headers=other)
    assert r.status_code == 404 and r.json()["error"]["code"] == "card_not_found"
    assert api.get("/v1/decks", headers=other).json() == {"items": []}
    assert conn.execute("select suspended from card").fetchone()["suspended"] is False
    assert learner_api.patch("/v1/cards/999", json={"suspended": True}).status_code == 404


def test_a_body_without_the_flag_is_refused_and_mock_mode_answers(learner_api, mock_client):
    assert learner_api.patch("/v1/cards/1", json={}).status_code == 422
    assert mock_client.get("/v1/decks").status_code == 200
    assert mock_client.patch("/v1/cards/17", json={"suspended": True}).status_code == 200
