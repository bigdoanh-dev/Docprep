"""Rerank and sufficiency gate on the hybrid pool (app/chat/rerank.py). Needs no database."""
import pytest

from app.chat import rerank
from app.chat.retrieval import Found, Passage
from app.chat.worker import TurnModelUnavailable, TurnStopped
from app.gateway import GatewayError


def p(i: int) -> Passage:
    return Passage(id=f"yhdp:d:{i}", document_id="d", document_title="Dengue", chapter="C", section="S",
                   page_start=None, article=None, text=f"Đoạn số {i}.", score=1 / (60 + i))


POOL = Found([p(i) for i in range(1, 9)])


def asker(scores=None, error=None, reply=None):
    calls = []

    def ask(system, user):
        calls.append(user)
        if error:
            raise error
        return reply if reply is not None else {"scores": {f"P{i + 1}": s for i, s in enumerate(scores)}}
    ask.calls = calls
    return ask


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    monkeypatch.setattr(rerank, "cfg", lambda: {"enabled": True, "pool": 30, "top_k": 3, "min_score": 2, "passage_chars": 1200})


def ids(found):
    return [x.id.rsplit(":", 1)[-1] for x in found.passages]


def test_the_best_scored_passages_are_sent_ties_keep_the_rrf_order():
    out = rerank.apply(asker([1, 3, 0, 2, 3, 0, 2, 1]), "q", POOL)
    assert ids(out.found) == ["2", "5", "4"] and not out.gated and out.failure is None and out.top_score == 3
    assert [x.score for x in out.found.passages] == [3.0, 3.0, 2.0]


def test_unrelated_passages_are_never_sent_even_to_fill_top_k():
    out = rerank.apply(asker([3, 0, 0, 0, 0, 0, 0, 0]), "q", POOL)
    assert ids(out.found) == ["1"]


def test_below_the_threshold_nothing_is_sent_and_the_turn_is_gated():
    out = rerank.apply(asker([1, 1, 0, 1, 0, 0, 0, 0]), "Vắc xin viêm não Nhật Bản tiêm mấy mũi?", POOL)
    assert out.gated and out.found.passages == [] and out.found.nearest == POOL.passages[0] and out.top_score == 1


@pytest.mark.parametrize("error", [GatewayError("down"), TurnModelUnavailable("model_unavailable")],
                         ids=["gateway", "chat worker (quota, overload)"])
def test_a_failed_call_keeps_the_rrf_top_k_without_a_gate(error):
    out = rerank.apply(asker(error=error), "q", POOL)
    assert ids(out.found) == ["1", "2", "3"] and not out.gated and out.failure == "model_error"


@pytest.mark.parametrize("reply", [{}, {"scores": []}, {"scores": {"P1": "high"}}, {"scores": {"x": 3}}])
def test_a_malformed_reply_keeps_the_rrf_top_k(reply):
    out = rerank.apply(asker(reply=reply), "q", POOL)
    assert ids(out.found) == ["1", "2", "3"] and out.failure == "malformed"


def test_an_unscored_passage_counts_as_unrelated():
    out = rerank.apply(asker(reply={"scores": {"P4": 2, "3": 3}}), "q", POOL)   # "3" without the P is accepted
    assert ids(out.found) == ["3", "4"]


@pytest.mark.parametrize("code", ["ai_cancelled", "ai_timeout", "ai_interrupted"])
def test_a_stopped_turn_still_stops(code):
    with pytest.raises(TurnStopped, match=code):
        rerank.apply(asker(error=TurnStopped(code)), "q", POOL)


def test_the_prompt_numbers_every_pooled_passage_and_trims_long_ones(monkeypatch):
    monkeypatch.setattr(rerank, "cfg", lambda: {"enabled": True, "pool": 30, "top_k": 3, "min_score": 2, "passage_chars": 6})
    ask = asker([0] * 8)
    rerank.apply(ask, "Câu hỏi thử", POOL)
    msg = ask.calls[0]
    assert msg.startswith("Câu hỏi: Câu hỏi thử\n\n") and "[P8] (Dengue › C › S)\nĐoạn s" in msg and "Đoạn số 8." not in msg


def test_an_empty_pool_is_passed_through_without_a_call():
    ask = asker([3])
    out = rerank.apply(ask, "q", Found([]))
    assert out.found.passages == [] and not out.gated and ask.calls == []
