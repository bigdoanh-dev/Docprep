"""What the ported services share: the activity log, content queries, safe retries, card text."""
from datetime import datetime, timezone

from app import events
from app.engine.cards import ORIGIN, card_text
from app.repo import content
from app.services.idempotency import run_once

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)


def test_events_are_recorded_under_the_pseudonym_with_a_capped_duration(conn):
    events.record(conn, "HV-1", "unit_response", NOW, duration_ms=41_000, ref_type="question", ref_id="q-dt-01")
    events.record(conn, "HV-1", "card_review", NOW, duration_ms=9_000_000, ref_type="card", ref_id=7)
    rows = conn.execute("select learner_pid, kind, duration_ms, ref_id from activity_event order by id").fetchall()
    assert rows == [{"learner_pid": "HV-1", "kind": "unit_response", "duration_ms": 41_000, "ref_id": "q-dt-01"},
                    {"learner_pid": "HV-1", "kind": "card_review", "duration_ms": 600_000, "ref_id": "7"}]


def test_only_the_approved_version_is_served(conn, learner):
    q = content.approved_question(conn, "q-dt-01")
    assert q["status"] == "approved" and q["version"] == 1
    conn.execute("update question set status = 'retired' where id = 'q-dt-01'")
    assert content.approved_question(conn, "q-dt-01") is None
    assert content.question_as_served(conn, "q-dt-01", None)["status"] == "retired"
    assert content.approved_question(conn, "nope") is None and content.question_as_served(conn, "nope", None) is None


def test_citations_keep_the_order_asked_and_skip_unknown_passages(conn, learner):
    cited = content.citations_for(conn, ["tc-p02", "nope", "dt-p01"])
    assert [(c["n"], c["passage_id"], c["page"]) for c in cited] == [(1, "tc-p02", 8), (3, "dt-p01", 58)]
    assert cited[0]["document"] == "Lịch tiêm chủng mở rộng"


def test_topics_are_the_leaf_nodes_with_their_hoc_phan(conn, learner):
    topics = {t["code"]: t for t in content.topics(conn)}
    assert len(topics) == 55 and "G1" not in topics
    assert topics["CI-04"]["module_id"] == "g1" and topics["CI-20"]["module_id"] == "g4"
    assert topics["FND"]["module_id"] == "g1" and topics["FND"]["weight"] == 2.0
    assert topics["CI-04"]["name"] == "Tiêm phòng/Tiêm chủng trẻ em và người lớn"


def test_run_once_returns_the_stored_answer_for_a_repeated_key(conn):
    calls = []

    def work():
        calls.append(1)
        return {"n": len(calls), "at": NOW}

    first = run_once(conn, "k1", "HV-1", "POST /x", work)
    again = run_once(conn, "k1", "HV-1", "POST /x", work)
    assert len(calls) == 1 and again == first and isinstance(again["at"], str)
    assert run_once(conn, "k1", "HV-2", "POST /x", work)["n"] == 2        # another learner, same key
    assert run_once(conn, None, "HV-1", "POST /x", work)["n"] == 3        # no key: no memory


def test_card_text_is_the_demo_wording(conn, learner):
    front, back = card_text(content.approved_question(conn, "q-dt-01"))
    assert front.startswith("Một xã có 2.000 dân") and back.startswith("Đáp án: 2,5%\n\n50 ÷ 2.000")
    assert ORIGIN["diagnostic"] == "Từ bài đánh giá" and ORIGIN["practice"] == ORIGIN["unit"]


def test_the_passage_view_cuts_the_excerpt_to_the_documents_limit(conn, learner):
    conn.execute("update document set excerpt_limit = 40 where id = (select document_id from passage where id = 'tc-p02')")
    view = content.passage_view(conn, "tc-p02")
    assert view["page"] == 8 and len(view["excerpt"]) <= 41 and view["excerpt"].endswith("…")
    assert set(view) == {"id", "document", "chapter", "section", "page", "article", "excerpt", "demo_label", "validity_note"}
    assert content.passage_view(conn, "nope") is None


def test_the_learner_api_client_is_signed_in_and_uses_the_fake_model(learner_api, fake_gw):
    from app.api import deps as api_deps

    assert learner_api.get("/v1/me").status_code == 200
    assert learner_api.app.dependency_overrides[api_deps.get_gateway]() is fake_gw
