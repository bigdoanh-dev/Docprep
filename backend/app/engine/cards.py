"""Rule-built revision cards from wrong answers (handover/05-algorithms.md §6, R1.0). Pure."""

# Where a card came from, as the learner reads it, by the context of the wrong answer.
ORIGIN = {"unit": "Từ quiz học phần", "practice": "Từ quiz học phần", "diagnostic": "Từ bài đánh giá",
          "mock": "Từ đề thi thử"}


def citation_for(passage: dict, document_title: str) -> str:
    if passage.get("page_start"):
        return f"{document_title}, tr. {passage['page_start']}"
    return f"{document_title}, {passage['article']}"


def card_text(question: dict) -> tuple[str, str]:
    """Front and back of the card built from an approved question: the stem, then the answer and
    the expert explanation."""
    answer = next(o["text"] for o in question["options"] if o["is_correct"])
    return question["stem"], f"Đáp án: {answer}\n\n{question['explanation']}"
