"""Prompt assembly: the allowlist, the exact text each turn sends, and the budget. Needs no database."""
import pytest

from app.chat.compose import ALLOWED_KINDS, Part, compose, estimate_tokens
from app.chat.retrieval import Passage


def passage(pid: str, text: str = "Nội dung đoạn.", page: int | None = 12, article: str | None = None) -> Passage:
    return Passage(id=pid, document_id="D", document_title="Dịch tễ học", chapter="C", section="S",
                   page_start=page, article=article, text=text, score=1.0)


def old_block(passages) -> str:
    """The evidence block as pipeline.py wrote it before compose existed."""
    return "\n\n".join(f"[{p.id}] ({p.document_title}, {'tr. ' + str(p.page_start) if p.page_start else p.article})\n{p.text}"
                       for p in passages)


PASSAGES = [passage("p1"), passage("p2", "Điều 5 nói rõ.", page=None, article="Điều 5")]


def test_only_allowlisted_kinds_exist():
    # learner_profile carries presentation rules only (app/chat/personalize.py), never learner data;
    # verified_claims carries stage A's checked claims to the layout stage (app/chat/adapt.py).
    assert ALLOWED_KINDS == {"question", "instruction", "previous_answer", "item", "learner_profile", "verified_claims"}
    for kind in ("pseudonym", "session_id", "learner", "persona", "memory", "time", "ip", "device"):
        with pytest.raises(ValueError):
            Part(kind, "x")


@pytest.mark.parametrize("detail", [False, True])
def test_a_chat_question_sends_the_same_text_as_before(detail):
    old = "Câu hỏi: Tỷ lệ hiện mắc là gì?\n"
    parts = [Part("question", "Câu hỏi: Tỷ lệ hiện mắc là gì?\n")]
    if detail:
        old += "Yêu cầu thêm: giải thích chi tiết hơn câu trả lời trước.\n"
        parts.append(Part("instruction", "Yêu cầu thêm: giải thích chi tiết hơn câu trả lời trước.\n"))
    old += f"\nPassages:\n{old_block(PASSAGES)}"
    parts.append(Part("instruction", "\n"))
    sent = compose(parts, PASSAGES, system="hệ thống")
    assert sent.user == old and sent.passages == PASSAGES and sent.dropped == 0


def test_tutor_and_quiz_chat_send_the_same_text_as_before():
    item = "Câu hỏi: ...\nĐáp án đúng: A"
    assert compose([Part("item", f"{item}\n\n")], PASSAGES).user == f"{item}\n\nPassages:\n{old_block(PASSAGES)}"
    quiz = compose([Part("item", f"{item}\n\n"), Part("question", "Câu hỏi của học viên: vì sao?\n\n")], PASSAGES).user
    assert quiz == f"{item}\n\nCâu hỏi của học viên: vì sao?\n\nPassages:\n{old_block(PASSAGES)}"


def test_a_hint_keeps_its_own_source_label():
    from app.services.hints import _user_message
    question = {"stem": "Thân câu?", "options": [{"key": "A", "text": "Một"}, {"key": "B", "text": "Hai"}]}
    sources = "\n\n".join(f"[{p.id}] ({p.document_title})\n{p.text}" for p in PASSAGES)
    assert _user_message(question, PASSAGES) == f"Câu hỏi: Thân câu?\nCác phương án:\nA. Một\nB. Hai\n\nPassages:\n{sources}"


def test_over_budget_drops_the_lowest_ranked_passages_whole():
    long = [passage(f"p{i}", "x" * 300) for i in range(5)]
    whole = compose([Part("question", "Q\n")], long, max_tokens=10_000)
    limit = estimate_tokens(whole.user) - 150          # room for about three passages
    sent = compose([Part("question", "Q\n")], long, max_tokens=limit)
    assert [p.id for p in sent.passages] == ["p0", "p1", "p2"] and sent.dropped == 2
    assert estimate_tokens(sent.user) <= limit
    assert all(p.text in sent.user for p in sent.passages)


def test_the_best_passage_is_always_kept():
    sent = compose([Part("question", "Q\n")], [passage("p1", "y" * 5000), passage("p2")], max_tokens=10)
    assert [p.id for p in sent.passages] == ["p1"] and sent.dropped == 1


def test_the_system_prompt_counts_toward_the_budget():
    two = [passage("p1", "z" * 300), passage("p2", "z" * 300)]
    fits = estimate_tokens(compose([], two, max_tokens=10_000).user)
    assert compose([], two, max_tokens=fits).dropped == 0
    assert compose([], two, system="s" * 600, max_tokens=fits).dropped == 1


def test_the_configured_budget_fits_the_demo_corpus():
    """With the shipped config nothing is dropped from a normal turn: behaviour is unchanged."""
    from app.config import settings
    budget = settings()["chat"]["prompt_token_budget"]
    top_k = settings()["retrieval"]["top_k"]
    typical = [passage(f"p{i}", "v" * 1500) for i in range(top_k)]
    assert compose([Part("question", "Q\n")], typical, system="s" * 4000).dropped == 0 and budget >= 4000
