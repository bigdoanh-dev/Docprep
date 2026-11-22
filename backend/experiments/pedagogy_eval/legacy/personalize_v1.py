"""FROZEN copy of app/chat/personalize.py as of commit 97e27dd (v1: mastery levels), the baseline of experiments/pedagogy_eval."""
"""Learner-adapted presentation: how an answer is laid out for this learner, decided in code.

The learner's records (owned by Business, read here only) are turned into a small Policy by fixed
rules, and the Policy into a short instruction block. The model never sees numbers about the learner
or anything that identifies them: only what to do. The block is used only by the layout stage
(app/chat/adapt.py), after the grounded answer has been written and checked: it never reaches the
call that decides whether the passages answer the question, and a policy never removes a claim.

Pedagogy (decided 2026-11-19): a weak topic gets a basic but fuller answer, with a definition, reason
or example added only when a passage states it; a strong topic gets a compact answer, figures first.

A learner gets a policy only when the personalization consent is active and there are enough answers
on the competencies the passages cover; otherwise the turn is exactly as before.
"""
from dataclasses import dataclass
from typing import Literal

from app.config import settings
from app.engine.elo import mastery_of
from app.repo import consent

Level = Literal["co_ban", "trung_binh", "nang_cao"]


@dataclass(frozen=True)
class Signals:
    mastery: float | None            # over the competencies of the passages read, weighted by answers
    n_responses: int                 # answers behind `mastery`
    recall_accuracy: float | None    # share correct on Bloom 1–2 items, all competencies
    applied_accuracy: float | None   # share correct on Bloom 3–6 items


@dataclass(frozen=True)
class Policy:
    level: Level
    additions: int           # sentences beyond the verified claims, each stated by a passage
    plain_wording: bool      # short sentences, terms and abbreviations explained where a passage does
    give_reasons: bool       # prefer reasons and conditions (remembers but does not apply)
    thresholds_first: bool   # figures, cut-offs and criteria before the rest


def cfg() -> dict:
    return settings()["personalization"]


def policy_for(s: Signals, c: dict | None = None) -> Policy | None:
    """The fixed rules. None means: not enough known about this learner, answer as for anyone."""
    c = c or cfg()
    if s.mastery is None or s.n_responses < c["min_responses"]:
        return None
    if s.mastery < c["low"]:
        level = "co_ban"
    elif s.mastery < c["high"]:
        level = "trung_binh"
    else:
        level = "nang_cao"
    gap = (s.recall_accuracy is not None and s.applied_accuracy is not None
           and s.recall_accuracy - s.applied_accuracy >= c["recall_applied_gap"])
    return Policy(level, c["additions"][level] + (c["reason_additions"] if gap else 0),
                  plain_wording=level == "co_ban", give_reasons=gap, thresholds_first=level == "nang_cao")


_LEVEL_VI = {"co_ban": "còn yếu ở chủ đề này",
             "trung_binh": "đã nắm cơ bản chủ đề này",
             "nang_cao": "đã vững chủ đề này"}


def profile_text(p: Policy) -> str:
    """The instruction block for the layout stage: what to do, never data about the learner."""
    lines = ["Hồ sơ người học (chỉ để chọn cách trình bày, không phải nguồn kiến thức):",
             f"- Trình độ: {_LEVEL_VI[p.level]}.",
             "- Luôn giữ ý trả lời trực tiếp câu hỏi trước; các quy tắc dưới đây chỉ đổi thứ tự, cách viết "
             "và phần bổ sung, không bao giờ bỏ ý nào."]
    if p.plain_wording:
        lines.append("- Trình bày cơ bản nhưng đủ ý, kỹ hơn bình thường: câu ngắn, từ ngữ dễ hiểu; giải nghĩa "
                     "thuật ngữ hoặc chữ viết tắt khi đoạn tài liệu có giải nghĩa.")
    if p.thresholds_first:
        lines.append("- Cô đọng, dùng đúng thuật ngữ chuyên môn. Sau ý trả lời trực tiếp, đưa các ý có con số, "
                     "ngưỡng, tiêu chí lên trước.")
    if p.give_reasons:
        lines.append("- Người học thuộc nhưng hay sai khi vận dụng: ưu tiên nêu lý do, điều kiện hoặc khi nào áp dụng.")
    if p.additions:
        lines.append(f"- Được thêm tối đa {p.additions} câu bổ sung (định nghĩa, lý do, điều kiện, hoặc ví dụ) "
                     "chỉ khi đoạn tài liệu viết đúng điều đó. Không tự nghĩ ra ví dụ.")
    else:
        lines.append("- Không thêm câu bổ sung.")
    return "\n".join(lines) + "\n\n"


# ---- reading the learner's records (Business owns them; Chat has SELECT only) ----------------------

def signals(conn, learner_id: int, competency_codes: list[str]) -> Signals:
    rows = conn.execute("select theta, n_responses from mastery where learner_id = %s and competency_code = any(%s)",
                        (learner_id, competency_codes)).fetchall() if competency_codes else []
    n = sum(r["n_responses"] for r in rows)
    mastery = sum(mastery_of(r["theta"]) * r["n_responses"] for r in rows) / n if n else None
    b = conn.execute(
        """select count(*) filter (where lvl <= 2) as recall_n, count(*) filter (where lvl <= 2 and correct) as recall_ok,
                  count(*) filter (where lvl >= 3) as applied_n, count(*) filter (where lvl >= 3 and correct) as applied_ok
           from (select coalesce(q.bloom_level_6, q.bloom_level) as lvl, r.correct
                 from item_response r join question q on q.id = r.question_id and q.version = r.question_version
                 where r.learner_id = %s) t""", (learner_id,)).fetchone()
    least = cfg()["min_bloom_items"]
    return Signals(mastery, n,
                   b["recall_ok"] / b["recall_n"] if b["recall_n"] >= least else None,
                   b["applied_ok"] / b["applied_n"] if b["applied_n"] >= least else None)


def for_turn(conn, learner_id: int | None, competency_codes: list[str]) -> Policy | None:
    """The policy for this turn, or None: switched off, no consent, or too little known."""
    if learner_id is None or not cfg()["enabled"] or consent.active(conn, learner_id, "personalization") is None:
        return None
    return policy_for(signals(conn, learner_id, competency_codes))
