"""Cited answers (design §6 answer contract, first cut): sources are numbered [S1]..[Sk],
the model must cite them after each claim, and citations resolve to document + section/page.
"""

import re
import sqlite3
from collections.abc import Iterator

from yhdp.retrieve import Hit

SYSTEM = """Bạn là trợ lý ôn thi NLHN Bác sĩ Y học dự phòng.
Quy tắc:
- Chỉ trả lời dựa trên các NGUỒN được cung cấp. Không dùng kiến thức ngoài nguồn.
- Ghi trích dẫn ngay sau mỗi ý, dạng [S1] hoặc [S1][S3]. Không trích dẫn nguồn không chứa ý đó.
- Nếu các nguồn không đủ để trả lời, nói rõ "Tài liệu hiện có không đề cập đến …" rồi dừng, không suy đoán.
- Giữ nguyên thuật ngữ y khoa, tên thuốc, liều lượng, đơn vị và ngưỡng số như trong nguồn.
- Trình bày bằng Markdown: tiêu đề ngắn, gạch đầu dòng; dùng bảng khi so sánh hoặc khi nguồn là bảng (liều theo lứa tuổi, phân độ…).
- Trả lời bằng tiếng Việt, ngắn gọn, đúng trọng tâm câu hỏi."""

CITE = re.compile(r"\[S(\d+)\]")


def citation(con: sqlite3.Connection, hit: Hit) -> str:
    """'QĐ 2760/QĐ-BYT (2023) — Hướng dẫn … › IV. ĐIỀU TRỊ › C.1. …' or '… tr. 54–55'."""
    doc = con.execute("SELECT * FROM documents WHERE doc_id = ?", (hit.doc_id,)).fetchone()
    issuer = f"{doc['issuer']} ({doc['year']})" if doc["issuer"] else doc["title"]
    head = f"{issuer} — {doc['title']}" if doc["issuer"] else issuer
    if doc["citation"] == "page" and hit.loc.printed_pages:
        pages = hit.loc.printed_pages
        return f"{head}, tr. {pages[0]}" + (f"–{pages[-1]}" if len(pages) > 1 else "")
    return f"{head} › " + " › ".join(hit.loc.section_path)


def build_messages(con: sqlite3.Connection, question: str, hits: list[Hit],
                   history: list[dict] | None = None, system: str = SYSTEM) -> list[dict]:
    blocks = []
    for i, h in enumerate(hits, start=1):
        label = {"table": "Bảng", "figure": "Hình", "box": "Hộp"}.get(h.kind, "")
        body = h.text if h.kind != "figure" else (h.extra.get("caption") or h.text)
        blocks.append(f"[S{i}] {citation(con, h)}" + (f" ({label})" if label else "") + f"\n{body}")
    user = "NGUỒN:\n\n" + "\n\n---\n\n".join(blocks) + f"\n\n=====\nCÂU HỎI: {question}"
    return [{"role": "system", "content": system}, *(history or []), {"role": "user", "content": user}]


def strip_citations(text: str) -> str:
    """For earlier turns sent as history: their [S#] point at that turn's sources, not this
    one's, and would mislead the model."""
    return CITE.sub("", text)


def cited(answer: str, n_sources: int) -> tuple[list[int], list[int]]:
    """(valid source numbers cited, out-of-range numbers) — the cite-or-abstain check."""
    nums = sorted({int(m) for m in CITE.findall(answer)})
    return [n for n in nums if 1 <= n <= n_sources], [n for n in nums if not 1 <= n <= n_sources]


def stream_answer(llm, con, question: str, hits: list[Hit], think: bool = False,
                  history: list[dict] | None = None) -> Iterator[str]:
    yield from llm.stream(build_messages(con, question, hits, history), temperature=0.1, think=think)
