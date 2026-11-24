"""Deterministic metadata. Questions always carry a literal evidence excerpt."""
import re
import unicodedata
from collections import Counter

from .chunk import Chunk

VERSION = "source-augmentation.v1"
_STOP = set("này trong được theo những các của hoặc một khi với cần cho không đến phần mục phụ lục".split())


def fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def terms(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", fold(text), re.UNICODE)


def role_of(path: list[str]) -> str:
    for heading in reversed(path):
        title = re.sub(r"^\s*(?:[a-z]+(?:\.\d+)*|[a-z]?\d+(?:\.\d+)*)[.)]\s+", "", fold(heading))
        for pattern, role in ((r"^(ví dụ|minh họa)\b", "example"),
                              (r"^(bài tập|câu hỏi ôn tập|bài thực hành)\b", "exercise"),
                              (r"^(lý thuyết|đại cương|tổng quan|định nghĩa)\b", "theory")):
            if re.match(pattern, title):
                return role
    return "unknown"


def augment(chunks: list[Chunk], title: str) -> list[dict]:
    figures = Counter((c.loc.anchor, c.text) for c in chunks if c.kind == "figure")
    result = []
    for chunk in chunks:
        path = chunk.loc.section_path
        leaf = path[-1] if path else title
        role = role_of(path)
        header = " › ".join([title, *path])
        if chunk.caption and chunk.caption != leaf:
            header += " › " + chunk.caption
        if role != "unknown":
            header += " › " + {"example": "Ví dụ", "exercise": "Bài tập", "theory": "Lý thuyết"}[role]
        counts = Counter(t for t in terms(chunk.text) if len(t) > 2 and t not in _STOP and not t.isdecimal())
        keywords = list(dict.fromkeys([k for k in terms(leaf) if k in counts] + [k for k, _ in counts.most_common(8)]))[:8]
        question = None
        if chunk.kind == "table" and chunk.text.lstrip().startswith("|"):
            question = {"question": f"Bảng trong mục «{leaf}» có các cột nào?",
                        "evidence": chunk.text.splitlines()[0]}
        elif chunk.kind == "figure" and chunk.caption and figures[(chunk.loc.anchor, chunk.text)] == 1:
            question = {"question": f"Hình nào trong Phụ lục hoặc mục «{leaf}» có chú thích «{chunk.caption}»?",
                        "evidence": chunk.text.splitlines()[0]}
        elif chunk.kind in {"text", "box"} and keywords:
            for line in chunk.text.splitlines():
                for sentence in re.split(r"(?<=[.!?;])\s+(?=[A-ZÀ-Ỹ])", line):
                    excerpt = sentence.strip()
                    matches = [word for word in keywords if word in terms(excerpt)]
                    if 35 <= len(excerpt) <= 340 and matches:
                        question = {"question": f"Trong mục «{leaf}», tài liệu nêu thông tin gì liên quan đến «{matches[0]}»?",
                                    "evidence": excerpt}
                        break
                if question:
                    break
        loc = chunk.loc.model_dump()
        loc["augmentation"] = {
            "version": VERSION, "contextual_header": header, "pedagogical_role": role,
            "parent_id": f"{chunk.doc_id}#{chunk.loc.anchor}", "keywords": keywords,
            "questions": [question] if question else [],
            "question_status": "draft" if question else "needs_review",
            "figure_asset": chunk.figure_path,
        }
        result.append({**chunk.model_dump(exclude={"loc"}), "location": loc})
    return result
