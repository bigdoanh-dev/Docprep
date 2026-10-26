"""Chat pipeline (handover/04-agentic-core.md).

pre-gate (code) → normalise → retrieve (code, always) → one model call → post-check tier 1
(code) → optional tier 2 (model) → one of answered / insufficient_evidence / declined /
needs_clarification. The answer text is released only after the post-check; nothing partial is
ever shown.

A turn runs in two parts. `prepare_*` does what code decides, on the database, and reports each stage
as a step while it runs; it ends with what the model is to be asked, or with the outcome when no
model call is needed. `generate` asks the model and checks its answer; it needs no database, so the
caller holds no connection while it waits.
"""
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Literal

from app.chat import clarify, trace
from app.chat.normalise import normalise
from app.chat.postcheck import Claim, Evidence, check_tier1
from app.chat.pregate import PREGATE_PATH, is_patient_specific, load_patterns
from app.chat.retrieval import Passage, find, get_passages
from app.chat.trace import Step
from app.config import settings
from app.gateway import Gateway, GatewayError, ModelResult
from app.repo import content

DECLINED_COPY = "Mình không tư vấn cho một ca bệnh cụ thể. Hãy liên hệ bác sĩ hoặc cơ sở y tế gần nhất."
INSUFFICIENT_COPY = "Tài liệu hiện có chưa đủ nội dung để trả lời câu này. Mình không đoán."
MODEL_DOWN_NOTICE = "Không kết nối được mô hình, vui lòng thử lại."
# For a turn that ended before the documents were weighed (model unreachable, system busy, a failure):
# it must not say the documents lack the answer. Its notice says why.
UNANSWERED_COPY = "Chưa trả lời được câu hỏi này lúc này."
REMOVED_NOTICE = "Đã bỏ {k} ý vì không tìm được nguồn trong giáo trình."
CLARIFY_COPY = 'Bạn muốn hỏi về nghĩa nào của "{term}"?'
PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
Event = tuple[str, object]
# No screen or answer may predict an exam outcome (FR-LRN-26); such claims are removed in code.
_PREDICTION = re.compile(r"(dự đoán điểm|xác suất đỗ|khả năng đỗ|khả năng đậu|điểm dự kiến|chắc chắn đỗ)", re.IGNORECASE)


@dataclass
class ChatOutcome:
    state: Literal["answered", "insufficient_evidence", "declined", "needs_clarification"]
    text: str
    citations: list[dict]
    retrieved_ids: list[str]
    model: ModelResult | None = None
    notice: str | None = None
    claims_checked: int | None = None      # claims the model produced; None when it produced no answer to check
    claims_removed: int | None = None      # of those, the ones the post-check dropped
    clarify_options: list[dict] = field(default_factory=list)
    searched: list[dict] = field(default_factory=list)
    nearest_chapter: dict | None = None
    cited_competencies: list[str] = field(default_factory=list)


@dataclass
class Prepared:
    """What code decided before any model call. `outcome` is set when the turn ends here; otherwise
    the rest says what to ask the model. `steps` are the stages that ran, in order; `generate` adds
    the post-check to them."""
    outcome: ChatOutcome | None
    steps: list[Step]
    task: str = ""
    system: str = ""
    user: str = ""
    passages: list[Passage] = field(default_factory=list)
    check_text: dict[str, str] = field(default_factory=dict)


@lru_cache
def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")


@lru_cache
def _pregate_rules():
    return load_patterns(PREGATE_PATH)


def parse_model_json(text: str) -> dict | None:
    """Accepts bare JSON, a ```json fence, or JSON embedded in prose; None when there is no object."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _source_label(p: Passage) -> str:
    return f"{p.document_title}, {'tr. ' + str(p.page_start) if p.page_start else p.article}"


def _passages_block(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{p.id}] ({_source_label(p)})\n{p.text}" for p in passages)


def _insufficient(retrieved_ids: list[str], model: ModelResult | None = None, notice: str | None = None,
                  **more) -> ChatOutcome:
    return ChatOutcome("insufficient_evidence", INSUFFICIENT_COPY, [], retrieved_ids, model, notice, **more)


# ---- where the system looked, for an answer it could not give ---------------------------------------

def _scope_searched(documents: list[dict]) -> list[dict]:
    """Every document retrieval looked in, with the pages its passages span."""
    def pages(d: dict) -> str:
        if d["first_page"] is None:
            return "toàn văn"
        return f"tr. {d['first_page']}" if d["first_page"] == d["last_page"] else f"tr. {d['first_page']}–{d['last_page']}"

    return [{"document": d["title"], "range": pages(d)} for d in documents]


def _read_searched(passages: list[Passage]) -> list[dict]:
    """The documents of the passages that were read, with the pages (or articles) read."""
    places: dict[str, list[str]] = {}
    for p in passages:
        place = str(p.page_start) if p.page_start else (p.article or "")
        seen = places.setdefault(p.document_title, [])
        if place and place not in seen:
            seen.append(place)
    return [{"document": title, "range": ("tr. " + ", ".join(where)) if where and where[0].isdigit() else (", ".join(where) or "toàn văn")}
            for title, where in places.items()]


def _nearest(passage: Passage | None) -> dict | None:
    """The chapter that came nearest, when anything shared a word with the question."""
    if passage is None:
        return None
    label = f"{passage.document_title} · {passage.chapter}" if passage.chapter else passage.document_title
    return {"passage_id": passage.id, "label_vi": label}


# ---- steps: a stage says when it starts and when it is done ----------------------------------------

def _begin(steps: list[Step], step: Step) -> Iterator[Event]:
    """Start a stage: it gets the next id and is announced as running. A turn shows at most
    `chat.max_steps` steps; a stage beyond that still runs, unannounced."""
    if len(steps) < settings()["chat"]["max_steps"]:
        steps.append(Step(f"s{len(steps) + 1}", step.kind, step.running_vi, step.done_vi))
        yield ("step", trace.event(steps[-1], "running"))


def _end(steps: list[Step], kind: str, done: Step | None = None) -> Iterator[Event]:
    """Finish the stage of that kind, if it was announced; `done` carries labels known only now."""
    for i, step in enumerate(steps):
        if step.kind == kind:
            if done is not None:
                steps[i] = Step(step.id, step.kind, step.running_vi, done.done_vi)
            yield ("step", trace.event(steps[i], "done"))


def _ask_model(gw: Gateway, task: str, system: str, user: str) -> tuple[dict | None, ModelResult]:
    """One call, plus one retry with the same prompt when the reply is not a JSON object."""
    version = settings()["prompt_versions"][task]
    messages = [{"role": "user", "content": user}]
    result = gw.complete(task, system, messages, version)
    data = parse_model_json(result.text)
    if data is None:
        result = gw.complete(task, system, messages, version)
        data = parse_model_json(result.text)
    return data, result


def _read_answer(data: dict) -> tuple[list[Claim], list[Evidence]]:
    """Read claims and evidence defensively: anything not shaped as asked is ignored, never an error."""
    def items(key: str) -> list:
        value = data.get(key)
        return value if isinstance(value, list) else []

    claims, evidence = [], []
    for e in items("evidence"):
        if isinstance(e, dict) and isinstance(e.get("passage_id"), str) and isinstance(e.get("quote"), str):
            evidence.append(Evidence(e["passage_id"], e["quote"]))
    for c in items("claims"):
        if isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"].strip():
            ids = c.get("passage_ids")
            claims.append(Claim(c["text"].strip(), [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []))
    return claims, evidence


def _check_tier2(gw: Gateway, claims: list[Claim], passages: dict[str, Passage]) -> list[Claim]:
    """One fixed model call: does the cited passage state the claim? Drops "no". Fails closed."""
    blocks = []
    for i, claim in enumerate(claims):
        cited = "\n".join(f"[{pid}] {passages[pid].text}" for pid in claim.passage_ids)
        blocks.append(f"Claim {i}: {claim.text}\nCited passages:\n{cited}")
    data, _result = _ask_model(gw, "check", _prompt("check_v1"), "\n\n".join(blocks))
    if data is None:
        return []
    raw = data.get("verdicts")
    verdicts = {v.get("i"): v.get("verdict") for v in (raw if isinstance(raw, list) else []) if isinstance(v, dict)}
    return [c for i, c in enumerate(claims) if verdicts.get(i) in ("yes", "partial")]


def _assemble(claims: list[Claim], passages: dict[str, Passage]) -> tuple[str, list[dict]]:
    order: list[str] = []
    parts = []
    for claim in claims:
        for pid in claim.passage_ids:
            if pid not in order:
                order.append(pid)
        markers = "".join(f"[{order.index(pid) + 1}]" for pid in dict.fromkeys(claim.passage_ids))
        parts.append(f"{claim.text} {markers}")
    citations = [{"n": n, "passage_id": pid, "document": passages[pid].document_title,
                  "chapter": passages[pid].chapter, "section": passages[pid].section,
                  "page": passages[pid].page_start, "article": passages[pid].article}
                 for n, pid in enumerate(order, start=1)]
    return " ".join(parts), citations


def generate(gw: Gateway, prepared: Prepared) -> Iterator[Event]:
    """The model call and the post-check: shared by chat, the tutor and the chat from a quiz item.
    Needs no database. Ends with ("done", outcome)."""
    passages, steps = prepared.passages, prepared.steps
    by_id = {p.id: p for p in passages}
    retrieved_ids = [p.id for p in passages]
    read = _read_searched(passages)

    yield ("status", "answering")
    try:
        data, result = _ask_model(gw, prepared.task, prepared.system, prepared.user)
    except GatewayError:
        yield ("done", ChatOutcome("insufficient_evidence", UNANSWERED_COPY, [], retrieved_ids, notice=MODEL_DOWN_NOTICE))
        return
    if data is None or data.get("insufficient") is True:
        yield ("done", _insufficient(retrieved_ids, result, searched=read))
        return

    yield ("status", "checking_sources")
    yield from _begin(steps, trace.check_step())
    claims, evidence = _read_answer(data)
    produced = len(claims)
    claims = check_tier1(claims, evidence, prepared.check_text)
    claims = [c for c in claims if not _PREDICTION.search(c.text)]
    if claims and settings()["postcheck"]["tier2_enabled"]:
        try:
            claims = _check_tier2(gw, claims, by_id)
        except GatewayError:
            yield from _end(steps, "check")
            yield ("done", ChatOutcome("insufficient_evidence", UNANSWERED_COPY, [], retrieved_ids, result, MODEL_DOWN_NOTICE))
            return
    yield from _end(steps, "check", trace.check_step(produced))
    removed = produced - len(claims)
    if not claims:
        yield ("done", _insufficient(retrieved_ids, result, claims_checked=produced, claims_removed=removed, searched=read))
        return
    text, citations = _assemble(claims, by_id)
    cited = list(dict.fromkeys(by_id[c["passage_id"]].competency_code for c in citations
                               if by_id[c["passage_id"]].competency_code))
    yield ("done", ChatOutcome("answered", text, citations, retrieved_ids, result,
                               notice=REMOVED_NOTICE.format(k=removed) if removed else None,
                               claims_checked=produced, claims_removed=removed, cited_competencies=cited))


def prepare_answer(conn, query: str, module_id: str | None = None, detail: bool = False,
                   clarifying: bool = False) -> Iterator[Event]:
    """A chat question: pre-gate, normalise, retrieve. Yields the steps as they run, then
    ("prepared", Prepared)."""
    if is_patient_specific(query, _pregate_rules()):
        yield ("prepared", Prepared(ChatOutcome("declined", DECLINED_COPY, [], []), []))
        return

    glossary = content.glossary(conn)
    # A term experts flagged as ambiguous is asked back before anything is searched. A turn that
    # already answers such a question is never asked again.
    asked_back = None if clarifying else clarify.options(query, glossary)
    if asked_back:
        term, senses = asked_back
        yield ("prepared", Prepared(ChatOutcome("needs_clarification", CLARIFY_COPY.format(term=term), [], [],
                                                clarify_options=senses), []))
        return

    steps: list[Step] = []
    normalised = normalise(query, glossary)
    looked_up = trace.glossary_step(list(normalised.matched))
    if looked_up:
        yield from _begin(steps, looked_up)
        yield from _end(steps, "lookup_glossary")

    module = content.module(conn, module_id) if module_id else None
    scope = content.documents_in_scope(conn, module_id)
    yield from _begin(steps, trace.search_step(len(scope), module["short_name"] if module else None))
    cfg = settings()["retrieval"]
    found = find(conn, normalised, cfg["top_k"], cfg["min_score"], module_id)
    yield from _end(steps, "search")
    if not found.passages:
        yield ("prepared", Prepared(_insufficient([], searched=_scope_searched(scope), nearest_chapter=_nearest(found.nearest)),
                                    steps))
        return

    yield from _begin(steps, trace.read_step(found.passages))
    user = f"Câu hỏi: {query}\n"
    if detail:
        user += "Yêu cầu thêm: giải thích chi tiết hơn câu trả lời trước.\n"
    user += f"\nPassages:\n{_passages_block(found.passages)}"
    yield from _end(steps, "read")
    yield ("prepared", Prepared(None, steps, "answer", _prompt("answer_v1"), user, found.passages,
                                {p.id: p.text for p in found.passages}))


def _item_block(question: dict, chosen: str | None) -> str:
    correct = next(o["key"] for o in question["options"] if o["is_correct"])
    options = "\n".join(f"{o['key']}. {o['text']} — ghi chú của chuyên gia: {o['rationale']}"
                        for o in question["options"])
    return (f"Câu hỏi: {question['stem']}\nCác phương án:\n{options}\nĐáp án đúng: {correct}\n"
            f"Học viên đã chọn: {chosen or 'không rõ'}\nGiải thích của chuyên gia: {question['explanation']}")


def prepare_explain(conn, question: dict, chosen: str | None = None) -> Iterator[Event]:
    """Tutor "Giải thích thêm": grounded only in the item's source passages and expert material."""
    steps: list[Step] = []
    yield from _begin(steps, trace.item_step())
    item = _item_block(question, chosen)
    yield from _end(steps, "get_item")
    by_id = get_passages(conn, question["source_passage_ids"])
    passages = [by_id[pid] for pid in question["source_passage_ids"] if pid in by_id]
    yield from _begin(steps, trace.read_step(passages))
    user = f"{item}\n\nPassages:\n{_passages_block(passages)}"
    yield from _end(steps, "read")
    # Numbers and quotes may come from the passages or from the expert material of this item.
    yield ("prepared", Prepared(None, steps, "tutor", _prompt("tutor_v1"), user, passages,
                                {p.id: f"{p.text}\n{item}" for p in passages}))


def prepare_quiz_chat(conn, question: dict, chosen: str | None, text: str) -> Iterator[Event]:
    """The first turn of a chat opened from a quiz item: the learner's own question about the item,
    answered from the item's source passages and expert material, the chosen option first. The
    pre-gate comes before anything else, as in every turn."""
    if is_patient_specific(text, _pregate_rules()):
        yield ("prepared", Prepared(ChatOutcome("declined", DECLINED_COPY, [], []), []))
        return
    steps: list[Step] = []
    yield from _begin(steps, trace.item_step())
    item = _item_block(question, chosen)
    yield from _end(steps, "get_item")
    by_id = get_passages(conn, question["source_passage_ids"])
    passages = [by_id[pid] for pid in question["source_passage_ids"] if pid in by_id]
    yield from _begin(steps, trace.read_step(passages))
    user = f"{item}\n\nCâu hỏi của học viên: {text}\n\nPassages:\n{_passages_block(passages)}"
    yield from _end(steps, "read")
    yield ("prepared", Prepared(None, steps, "quiz_chat", _prompt("quiz_chat_v1"), user, passages,
                                {p.id: f"{p.text}\n{item}" for p in passages}))
