"""Cited Q&A for the web app: retrieval + streamed answer as NDJSON events. The model may call
tools to create a topic quiz or add a card to the learner's revision deck, and after a plain
answer it suggests follow-up questions.

What the tutor does with the sources depends on the move (yhdp/api/tutor.py): explain, compare,
work an example, quiz the learner and grade the reply, or summarise. A comparison gathers sources
for each item compared; a move about "nội dung trên" uses the previous answer's sources.

A question that spans many chapters ("lập bảng triệu chứng các bệnh", "so sánh …") is first
planned: the model picks the chapters it needs from the corpus outline and the aspect to look for
in each, and the sources are the best chunks per chapter (Retriever.fan_out) instead of the six
nearest to the question's words.

Events, one JSON object per line:
  {"type": "plan", "mode": "…", "sections": ["…", ...], "aspect": "…"}  (synthesis, comparison)
  {"type": "sources", "sources": [{n, chunk_id, doc_id, kind, citation, text, figure_path}]}
  {"type": "delta", "text": "..."}            (repeated)
  {"type": "tool", "name": "...", "result": {"ok": bool, ...}}
  {"type": "done", "cited": [1, 3], "invalid": [], "tools": bool, "mode": "giai_thich"}
  {"type": "suggestions", "items": ["...", ...]}  (after done; may be absent)
  {"type": "error", "message": "..."}
"""

import json
import re
import sqlite3
from collections.abc import Iterator

from pydantic import BaseModel, Field

from yhdp.answer import SYSTEM, build_messages, citation, cited, strip_citations
from yhdp.api.tutor import (
    FOLLOW_ON,
    TEMPERATURE,
    Mode,
    instruct,
    plan_comparison,
    resolve_mode,
    unaccent,
)
from yhdp.dictionary import load_dictionary
from yhdp.llm import LLMError, Ollama
from yhdp.mcq import bank, deck
from yhdp.retrieve import Hit, Retriever, load_hits

MAX_HISTORY = 4  # previous messages sent to the model, for follow-up questions
MAX_CONTEXT = 4  # sources carried over from the previous answer, for "save that as a card"
TOOL_ROUNDS = 2  # a failed tool call can be retried once

TOOLS = [
    {"type": "function", "function": {
        "name": "tao_bai_trac_nghiem",
        "description": "Tạo một bài trắc nghiệm (không tính giờ) từ ngân hàng câu hỏi về một chủ "
                       "đề. CHỈ gọi khi người dùng yêu cầu rõ ràng tạo bài/đề/câu trắc nghiệm.",
        "parameters": {"type": "object", "required": ["chu_de"], "properties": {
            "chu_de": {"type": "string",
                       "description": "Chủ đề ngắn gọn bằng tiếng Việt có dấu, VD 'sốt xuất "
                                      "huyết Dengue ở trẻ em'"},
            "so_cau": {"type": "integer", "description": "Số câu, 5–30, mặc định 10"}}}}},
    {"type": "function", "function": {
        "name": "them_the_on_tap",
        "description": "Thêm một thẻ ghi nhớ vào bộ thẻ ôn tập của người dùng. CHỈ gọi khi người "
                       "dùng yêu cầu lưu/ghi nhớ/thêm thẻ.",
        "parameters": {"type": "object", "required": ["mat_truoc", "mat_sau"], "properties": {
            "mat_truoc": {"type": "string",
                          "description": "Câu hỏi ngắn để tự kiểm tra, ≤ 20 từ"},
            "mat_sau": {"type": "string",
                        "description": "Câu trả lời ngắn gọn (≤ 80 từ), giữ đúng con số, có "
                                       "trích dẫn [S#] từ NGUỒN"}}}}},
]

TOOL_SYSTEM = SYSTEM + """

Công cụ (chỉ gọi khi người dùng yêu cầu rõ ràng; câu hỏi kiến thức thì trả lời bình thường):
- tao_bai_trac_nghiem: khi người dùng muốn làm bài/đề/câu trắc nghiệm về một chủ đề. Nếu họ nói
  "chủ đề này", lấy chủ đề từ cuộc trò chuyện.
- them_the_on_tap: khi người dùng muốn lưu/ghi nhớ một ý. Nếu họ nói "câu trả lời trên", tóm
  tắt ý chính của câu trả lời trước thành một thẻ; mặt sau phải trích dẫn [S#] của NGUỒN hiện tại.
Không bao giờ tự soạn câu hỏi trắc nghiệm trong câu trả lời: câu hỏi chỉ lấy từ ngân hàng qua
công cụ."""

RETRY = ("Một công cụ chưa chạy được (xem kết quả). Nếu sửa được thì gọi lại công cụ; nếu không, "
         "giải thích ngắn gọn bằng một câu. Không tự soạn câu hỏi trắc nghiệm hay nội dung thẻ.")

SUGGEST = ("Gợi ý 3 câu hỏi tiếp theo mà người học có thể hỏi để hiểu sâu hơn chủ đề này. Mỗi câu "
           "ngắn (≤ 14 từ), trả lời được bằng các NGUỒN ở trên, không lặp lại câu đã hỏi, viết "
           "như người học đang hỏi.")


class Message(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Message] = Field(default_factory=list)
    context: list[str] = Field(default=[], max_length=10)  # chunk ids cited by the last answer
    k: int = Field(default=6, ge=1, le=10)
    mode: Mode = "auto"


class Suggestions(BaseModel):
    cau_hoi: list[str] = Field(max_length=3)


class Plan(BaseModel):
    chuong: list[int] = Field(max_length=16)
    khia_canh: str = Field(max_length=120)


# Words that ask for a list or table across topics; matched without diacritics. A comparison is
# its own move (tutor.py).
SYNTHESIS = re.compile(r"\b(lap bang|ke bang|danh sach|liet ke|tong hop|"
                       r"cac benh|nhung benh|moi benh|tung benh|tat ca)\b")

PLAN = """Câu hỏi dưới đây có thể cần tổng hợp thông tin từ nhiều chương của tài liệu.
Dựa vào MỤC LỤC, chọn số thứ tự các chương có nội dung cần cho câu trả lời (tối đa 16; bỏ qua
danh mục chữ viết tắt, mẫu giấy tờ và phụ lục không liên quan). Viết `khia_canh`: cụm từ ngắn mô
tả nội dung cần tìm trong mỗi chương, VD "triệu chứng lâm sàng", "phác đồ điều trị kháng sinh".
Nếu câu hỏi chỉ về một chủ đề hẹp nằm trong một chương, trả về danh sách chương rỗng.

MỤC LỤC:
{outline}

CÂU HỎI: {question}"""

SYNTHESIS_NOTE = ("\n\n(Nguồn được lấy từ từng chương liên quan để tổng hợp. Trình bày đủ mọi mục "
                  "có trong nguồn, mỗi mục kèm trích dẫn; mục nào nguồn không nêu thì ghi rõ.)")


def is_synthesis(question: str) -> bool:
    return bool(SYNTHESIS.search(unaccent(question)))


def plan_sources(llm: Ollama, retriever: Retriever,
                 question: str) -> tuple[list[Hit], list[str], str] | None:
    """(sources, chapter headings, aspect) for a question that spans chapters; None when the
    model finds it narrow, picks nothing usable, or fails (the caller then searches as usual)."""
    outline = retriever.outline()
    lines, title = [], None
    for i, (_, doc_title, heading) in enumerate(outline, start=1):
        if doc_title != title:
            lines.append(f"Tài liệu: {doc_title}")
            title = doc_title
        lines.append(f"  {i}. {heading or '(phần mở đầu)'}")
    try:
        plan = llm.chat([{"role": "user", "content": PLAN.format(outline="\n".join(lines),
                                                                  question=question)}],
                        schema=Plan, temperature=0.0, retries=1)
    except LLMError:
        return None
    picked = [outline[i - 1] for i in dict.fromkeys(plan.chuong) if 1 <= i <= len(outline)]
    if len(picked) < 2 or not plan.khia_canh.strip():
        return None
    hits = retriever.fan_out(plan.khia_canh, [(doc, heading) for doc, _, heading in picked])
    return hits, [heading for *_, heading in picked], plan.khia_canh.strip()


def _refs(con: sqlite3.Connection, hits: list[Hit]) -> list[dict]:
    hashes = {r["chunk_id"]: r["content_hash"] for r in con.execute(
        f"SELECT chunk_id, content_hash FROM chunks WHERE chunk_id IN "
        f"({','.join('?' * len(hits))})", [h.chunk_id for h in hits])} if hits else {}
    return [{"chunk_id": h.chunk_id, "content_hash": hashes[h.chunk_id]} for h in hits]


def run_tool(con: sqlite3.Connection, retriever: Retriever, username: str, call: dict,
             hits: list[Hit]) -> dict:
    """Execute one tool call; errors come back as {"ok": False, "message"} for the model."""
    args = call["arguments"]
    if call["name"] == "tao_bai_trac_nghiem":
        topic = str(args.get("chu_de") or "").replace("_", " ").strip()
        if not topic:
            return {"ok": False, "message": "Thiếu chủ đề."}
        try:
            size = int(args.get("so_cau") or 10)
        except (TypeError, ValueError):
            size = 10
        chunks, scoped = retriever.topic(topic)
        try:
            s = bank.create_topic_set(con, username, topic, chunks, scoped, size)
        except LookupError:
            return {"ok": False, "message": f"Ngân hàng chưa có câu hỏi nào về “{topic}”."}
        return {"ok": True, "set_id": s["id"], "title": topic, "size": len(s["items"]),
                "notes": s["notes"]}
    if call["name"] == "them_the_on_tap":
        front, back = str(args.get("mat_truoc") or ""), str(args.get("mat_sau") or "")
        if not front.strip() or not back.strip():
            return {"ok": False, "message": "Thẻ cần có cả mặt trước và mặt sau."}
        try:
            card = deck.add_chat_card(con, username, front, back, _refs(con, hits))
        except ValueError as e:
            return {"ok": False, "message": f"{e}. Hãy gọi lại công cụ với trích dẫn [S#]."}
        return {"ok": True, "card_id": card["id"], "front": card["front"], "text": card["text"]}
    return {"ok": False, "message": f"Không có công cụ {call['name']}."}


def suggestions(llm: Ollama, messages: list[dict], answer: str, question: str) -> list[str]:
    out = llm.chat([*messages, {"role": "assistant", "content": answer},
                    {"role": "user", "content": SUGGEST}], schema=Suggestions, temperature=0.3,
                   retries=1)
    seen = {question.strip().casefold()}
    items = []
    for q in out.cau_hoi:
        q = q.strip()
        if 5 < len(q) <= 140 and q.casefold() not in seen:
            seen.add(q.casefold())
            items.append(q)
    return items


def gather(con: sqlite3.Connection, llm: Ollama, retriever: Retriever, req: ChatRequest,
           mode: str) -> tuple[list[Hit], dict | None]:
    """The sources for this move, and the plan to announce when one was made."""
    earlier = [m for m in req.history[-MAX_HISTORY:] if m.role in ("user", "assistant")]
    if mode == "so_sanh":
        talk = "\n".join(f"{m.role}: {strip_citations(m.content)[:400]}" for m in earlier)
        if compared := plan_comparison(llm, retriever, req.question, talk):
            hits, items, criteria = compared
            return hits, {"sections": items, "aspect": ", ".join(criteria)}
    if (mode == "giai_thich" and is_synthesis(req.question)
            and (planned := plan_sources(llm, retriever, req.question))):
        hits, sections, aspect = planned
        return hits, {"sections": sections, "aspect": aspect}
    if mode in FOLLOW_ON and req.context:
        hits = load_hits(con, list(dict.fromkeys(req.context)))
        if mode != "cham":  # what was discussed, plus a little more around the same question
            topic = next((m.content for m in reversed(earlier) if m.role == "user"), req.question)
            have = {h.chunk_id for h in hits}
            hits += [h for h in retriever.search(topic, k=4) if h.chunk_id not in have]
        return hits, None
    return retriever.search(req.question, k=req.k), None


def chat_events(con: sqlite3.Connection, llm: Ollama, req: ChatRequest,
                username: str) -> Iterator[str]:
    def event(**data) -> str:
        return json.dumps(data, ensure_ascii=False) + "\n"

    retriever = Retriever(con, llm, dictionary=load_dictionary())
    mode = resolve_mode(req.mode, req.question)
    try:
        hits, plan = gather(con, llm, retriever, req, mode)
    except (LLMError, RuntimeError) as e:
        yield event(type="error", message=f"Không tìm được nguồn: {e}")
        return
    if plan:
        yield event(type="plan", mode=mode, **plan)
    synthesis = plan is not None and mode == "giai_thich"
    question = req.question + SYNTHESIS_NOTE if synthesis else instruct(mode, req.question)
    # Tools only when explaining: a quiz or card is asked for in plain words, never as a move.
    tools = TOOLS if mode == "giai_thich" else None
    have = {h.chunk_id for h in hits}
    hits += load_hits(con, [c for c in dict.fromkeys(req.context) if c not in have][:MAX_CONTEXT])
    yield event(type="sources", sources=[
        {"n": i, "chunk_id": h.chunk_id, "doc_id": h.doc_id, "kind": h.kind,
         "citation": citation(con, h), "text": h.text, "figure_path": h.extra.get("figure_path")}
        for i, h in enumerate(hits, start=1)])
    history = [{"role": m.role, "content": strip_citations(m.content)}
               for m in req.history[-MAX_HISTORY:] if m.role in ("user", "assistant")]
    messages = build_messages(con, question, hits, history=history, system=TOOL_SYSTEM)
    answer, used_tools = "", False
    try:
        for round_ in range(TOOL_ROUNDS + 1):
            text, calls = "", []
            if answer and not answer.endswith("\n"):
                answer += "\n\n"
                yield event(type="delta", text="\n\n")
            for piece in llm.stream_events(messages, tools=tools if round_ < TOOL_ROUNDS else None,
                                           temperature=TEMPERATURE.get(mode, 0.1)):
                if isinstance(piece, str):
                    text += piece
                    yield event(type="delta", text=piece)
                else:
                    calls.append(piece)
            answer += text
            if not calls:
                break
            used_tools = True
            messages.append({"role": "assistant", "content": text,
                             "tool_calls": [{"function": c} for c in calls]})
            failed = False
            for c in calls:
                result = run_tool(con, retriever, username, c, hits)
                failed |= not result["ok"]
                yield event(type="tool", name=c["name"], result=result)
                messages.append({"role": "tool", "tool_name": c["name"],
                                 "content": json.dumps(result, ensure_ascii=False)})
            if not failed:
                break  # the tool card says what happened; a model recap tends to invent questions
            messages.append({"role": "user", "content": RETRY})
    except LLMError as e:
        yield event(type="error", message=f"Mô hình không trả lời được: {e}")
        return
    used, bad = cited(answer, len(hits))
    yield event(type="done", cited=used, invalid=bad, tools=used_tools, mode=mode)
    if used_tools or not used or mode == "kiem_tra":  # a quiz question waits for its answer
        return
    try:
        if items := suggestions(llm, messages, answer, req.question):
            yield event(type="suggestions", items=items)
    except LLMError:
        pass  # suggestions are optional
