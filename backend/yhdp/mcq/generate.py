"""MCQ generation (design §7): one 4-option, single-best-answer item per target chunk.

Every distractor is purposeful: the model writes it together with why it is wrong and the
mistake that leads a learner to it, both cited ([S#]) and one sentence each. Letters are
assigned only after generation, so explanations never point at a stale letter.

Pipeline per item: write (LLM) → place the key on the least-used letter in the bank → deterministic checks (cueing, distinct options, numbers in the key found in the
source) → blind answer (LLM, sees source + item, not the key) → quality review (LLM: single
best answer, faithful, no cueing, Bloom level). Any failure discards the item; discarded items
are kept with their reasons for prompt tuning.

Distractors come from the source passages (alternative drugs, neighbouring thresholds, other
protocol steps) until the entity graph (design §4.4) exists.
"""

import json
import random
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from yhdp.blueprint import Blueprint, load_blueprint
from yhdp.ingest.model import Loc
from yhdp.ingest.tag import BLOOM, MCQ_ELIGIBLE
from yhdp.llm import LLMError, Ollama
from yhdp.mcq.allocate import largest_remainder
from yhdp.settings import settings
from yhdp.store.tags import effective_tags

LETTERS = ("A", "B", "C", "D")  # 4 options per item, as in the official exam
MIN_TOKENS = 40  # thinner chunks rarely support a vignette
CONTEXT_TOKENS = 1800
Letter = Literal["A", "B", "C", "D"]

BLOOM_TASK = {
    "Áp dụng": "áp dụng đúng một tiêu chuẩn, ngưỡng, liều hoặc bước xử trí vào tình huống cụ thể",
    "Phân tích": "diễn giải dữ kiện (triệu chứng, xét nghiệm, số liệu) để phân biệt hoặc tìm nguyên nhân",
    "Đánh giá": "cân nhắc và chọn phương án tốt nhất trong nhiều phương án đều có vẻ hợp lý "
                "(chỉ định/chống chỉ định, chuyển tuyến, đổi phác đồ)",
}


EXPLANATION_CHARS = 260  # "concise": about one sentence


OptionText = Annotated[str, Field(min_length=3)]  # the option text itself, never a bare letter


class Distractor(BaseModel):
    noi_dung: OptionText
    sai_vi: str = Field(max_length=EXPLANATION_CHARS)  # why it's wrong, with [S#]
    nham_lan: str = Field(max_length=EXPLANATION_CHARS)  # the mistake that leads here, with [S#]


class Generated(BaseModel):
    y_tuong: str  # first: the tested fact and the misconception behind each distractor
    tinh_huong: str
    cau_hoi: str
    noi_dung_dap_an_dung: OptionText
    giai_thich_dung: str = Field(max_length=EXPLANATION_CHARS)  # why it's right, with [S#]
    phuong_an_nhieu: list[Distractor] = Field(min_length=3, max_length=3)


class BlindAnswer(BaseModel):
    ly_do: str
    dap_an: Letter


class QualityReview(BaseModel):
    nhan_xet: str
    mot_dap_an_dung_nhat: bool
    dap_an_dung_theo_nguon: bool
    co_goi_y_lo_dap_an: bool
    bloom: Literal[BLOOM]


GEN_SYSTEM = """Bạn là chuyên gia ra đề thi trắc nghiệm NLHN Bác sĩ Y học dự phòng (câu hỏi \
tình huống, 4 phương án A–D, một đáp án đúng nhất, mức Áp dụng trở lên).
Quy tắc:
- Chỉ dùng kiến thức trong NGUỒN. Đáp án đúng phải được NGUỒN khẳng định trực tiếp; giữ nguyên \
liều, ngưỡng, đơn vị như trong nguồn.
- Tình huống 2–5 câu, bối cảnh tuyến ban đầu (trạm y tế, phòng khám, cộng đồng); có đủ dữ kiện \
(tuổi, giới, triệu chứng, chỉ số) để suy ra đáp án; không nhắc thẳng tên đáp án; KHÔNG chứa câu \
hỏi (câu hỏi chỉ nằm ở cau_hoi).
- noi_dung_dap_an_dung và noi_dung của phương án nhiễu là NỘI DUNG đầy đủ của phương án (VD: \
"Ceftriaxone 100 mg/kg/ngày"), không phải chữ cái A–D. Chữ cái được gán sau.
- Câu hỏi (cau_hoi) ngắn, rõ, hỏi "phù hợp nhất/đúng nhất". Không dùng phủ định ("KHÔNG", "ngoại trừ").
- Mỗi phương án nhiễu phải CÓ CHỦ ĐÍCH: ứng với một sai lầm cụ thể người học hay mắc, ví dụ \
nhầm ngưỡng/liều của nhóm khác (trẻ em ↔ người lớn), dùng phác đồ của mức độ khác, chọn thuốc \
thay thế khi chưa đủ điều kiện, bỏ sót một dữ kiện trong tình huống, nhầm thứ tự các bước. Phương \
án nhiễu cùng loại với đáp án (cùng là thuốc, liều, ngưỡng, bước xử trí…) và lấy từ nguồn khi có thể.
- Mỗi phương án NGẮN (tối đa ~15 từ), chỉ nêu nội dung (thuốc + liều, ngưỡng, hành động…), KHÔNG \
kèm lý do hay điều kiện giải thích. 4 phương án dài tương đương, cùng cấu trúc ngữ pháp.
- Tình huống không được để lộ đáp án (không nêu sẵn quyết định, tên thuốc hay hành động đúng).
- Không dùng "tất cả đều đúng/sai", "cả A và B". Không ghi chữ cái A–D trong giải thích.
- Giải thích NGẮN GỌN, mỗi ý một câu, luôn có trích dẫn [S#]:
  - giai_thich_dung: vì sao đáp án đúng.
  - sai_vi: vì sao phương án nhiễu sai.
  - nham_lan: người học chọn phương án này có thể đã nhầm ở đâu (VD: "Nhầm với liều cho người lớn [S1].").
- y_tuong (viết trước): kiến thức được kiểm tra, câu trong nguồn làm căn cứ, sai lầm mà mỗi phương án nhiễu nhắm tới."""

BLIND_SYSTEM = """Bạn là thí sinh giỏi. Đọc NGUỒN và câu hỏi trắc nghiệm, chọn MỘT đáp án đúng \
nhất theo NGUỒN. Trả về JSON đúng schema."""

REVIEW_SYSTEM = """Bạn thẩm định câu hỏi trắc nghiệm cho kỳ thi NLHN Bác sĩ Y học dự phòng, \
đối chiếu với NGUỒN. Đánh giá nghiêm khắc:
- mot_dap_an_dung_nhat: chỉ đúng một phương án là đúng nhất (không có phương án thứ hai cũng đúng).
- dap_an_dung_theo_nguon: đáp án được đánh dấu đúng và được NGUỒN khẳng định.
- co_goi_y_lo_dap_an: có gợi ý làm lộ đáp án (đáp án dài/chi tiết hơn hẳn, lặp từ khóa của tình \
huống, phương án nhiễu vô lý, ngữ pháp chỉ khớp với đáp án).
- bloom: mức nhận thức mà câu hỏi thực sự đòi hỏi (Nhớ, Hiểu, Áp dụng, Phân tích, Đánh giá). \
Câu chỉ cần nhớ lại một con số hay định nghĩa là Nhớ, dù có tình huống."""


@dataclass
class Target:
    chunk_id: str
    doc_id: str
    van_de: int
    de_muc: int
    mien: str
    bloom: str


# --- selecting targets --------------------------------------------------------------------

def eligible_chunks(con: sqlite3.Connection) -> list[dict]:
    """MCQ-eligible chunks (current tag: human if reviewed, else auto) with enough text."""
    tags = effective_tags(con)
    rows = {r["chunk_id"]: r for r in con.execute(
        "SELECT chunk_id, doc_id, kind, tokens, seq, parent_anchor FROM chunks")}
    out = []
    for cid, t in tags.items():
        r, rec = rows[cid], t["record"]
        if not rec["mcq_eligible"] or r["kind"] == "figure" or r["tokens"] < MIN_TOKENS:
            continue
        out.append({"chunk_id": cid, "doc_id": r["doc_id"], "record": rec, "seq": r["seq"]})
    return out


def plan_targets(con: sqlite3.Connection, n: int, van_de: int | None = None, seed: int = 0,
                 bp: Blueprint | None = None) -> list[Target]:
    """n targets spread over đề mục by blueprint midpoints (only those with eligible chunks),
    round-robin over vấn đề inside each, least-used chunks first."""
    bp = bp or load_blueprint()
    rnd = random.Random(seed)
    used = {r["cid"]: r["n"] for r in con.execute(
        "SELECT json_extract(sources, '$[0].chunk_id') AS cid, count(*) AS n FROM mcq_items "
        "WHERE status != 'discarded' GROUP BY cid")}
    by_van_de: dict[int, list[dict]] = {}
    for c in eligible_chunks(con):
        vd = next(v["id"] for v in c["record"]["blueprint"]["van_de"] if v["primary"])
        if van_de is None or vd == van_de:
            by_van_de.setdefault(vd, []).append(c)
    for chunks in by_van_de.values():
        rnd.shuffle(chunks)
        chunks.sort(key=lambda c: used.get(c["chunk_id"], 0))
    de_muc_of = {v.id: v.de_muc for v in bp.van_de}
    weights = {d.id: sum(d.weight) / 2 for d in bp.de_muc
               if any(de_muc_of[v] == d.id for v in by_van_de)}
    quota = largest_remainder(weights, n)
    targets = []
    for dm, k in quota.items():
        pools = sorted((v for v in by_van_de if de_muc_of[v] == dm),
                       key=lambda v: -len(by_van_de[v]))
        cursor = {v: 0 for v in pools}
        i = 0
        while k > 0 and pools:
            v = pools[i % len(pools)]
            chunks = by_van_de[v]
            c = chunks[cursor[v] % len(chunks)]
            cursor[v] += 1
            rec = c["record"]
            top_mien = max(rec["blueprint"]["mien"], key=lambda m: m["conf"])["id"]
            targets.append(Target(c["chunk_id"], c["doc_id"], v, dm, top_mien,
                                  rec["bloom_ceiling"]["level"]))
            k -= 1
            i += 1
    return targets


def source_context(con: sqlite3.Connection, chunk_id: str) -> list[sqlite3.Row]:
    """The target chunk plus up to two neighbours from the same section (distractor material)."""
    c = con.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
    siblings = con.execute(
        "SELECT * FROM chunks WHERE doc_id = ? AND parent_anchor = ? AND chunk_id != ? "
        "AND kind != 'figure' ORDER BY abs(seq - ?) LIMIT 2",
        (c["doc_id"], c["parent_anchor"], chunk_id, c["seq"])).fetchall()
    out, used = [c], c["tokens"]
    for s in siblings:
        if used + s["tokens"] <= CONTEXT_TOKENS:
            out.append(s)
            used += s["tokens"]
    return out


def sources_block(con: sqlite3.Connection, chunks: list[sqlite3.Row]) -> str:
    docs = {r["doc_id"]: r for r in con.execute("SELECT * FROM documents")}
    parts = []
    for i, c in enumerate(chunks, start=1):
        d, loc = docs[c["doc_id"]], Loc.model_validate_json(c["loc"])
        parts.append(f"[S{i}] {d['issuer'] or d['title']} › {' › '.join(loc.section_path)}\n{c['text']}")
    return "NGUỒN:\n\n" + "\n\n---\n\n".join(parts)


# --- deterministic checks -----------------------------------------------------------------

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# "Wrong because the source doesn't mention it" is not a reason: in medicine an unmentioned
# option can still be right (antibiotics for plague). A distractor must be wrong per the source.
ABSENCE = re.compile(r"(không|chưa) (được )?(đề cập|nhắc|nêu|ghi nhận|có trong)|nguồn không")
CUE_PHRASES = ("tất cả", "cả a và", "cả b và", "không có phương án", "đều đúng", "đều sai")


def _norm_number(s: str) -> str:
    return s.replace(".", "").replace(",", "")


def _fold(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).casefold()).strip()


CITE = re.compile(r"\[S(\d+)\]")


def check_item(options: dict[str, str], answer: str, source_text: str,
               explanations: dict[str, dict] | None = None, n_sources: int = 0) -> list[str]:
    problems = []
    for k, e in (explanations or {}).items():
        refs = [int(n) for part in e.values() if part for n in CITE.findall(part)]
        if not refs or any(not 1 <= n <= n_sources for n in refs):
            problems.append(f"explanation_{k}_uncited")
    texts = [_fold(options[k]) for k in LETTERS]
    if any(not t for t in texts) or len(set(texts)) < 4:
        problems.append("options_not_distinct")
    if any(p in t for t in texts for p in CUE_PHRASES):
        problems.append("all_none_of_the_above")
    key_len = len(options[answer])
    other = max(len(options[k]) for k in LETTERS if k != answer)
    if other and key_len > 1.5 * other and key_len - other > 20:
        problems.append("key_much_longer")
    source_numbers = {_norm_number(n) for n in NUMBER.findall(source_text)}
    for k in LETTERS:  # doses and thresholds, right or wrong, come from the source, not invented
        missing = [n for n in NUMBER.findall(options[k]) if _norm_number(n) not in source_numbers]
        if missing:
            role = "key" if k == answer else "distractor"
            problems.append(f"{role}_numbers_not_in_source:{','.join(missing)}")
    for k, e in (explanations or {}).items():
        if k != answer and ABSENCE.search(_fold(e.get("why") or "")):
            problems.append(f"distractor_{k}_wrong_only_by_absence")
    return problems


def assign_letters(gen: Generated, target: str,
                   rnd: random.Random) -> tuple[dict[str, str], dict[str, dict], str]:
    """Put the key on `target` and the shuffled distractors on the other letters.
    Explanations: {"A": {"correct": True, "why": …}, "B": {"correct": False, "why": …,
    "mistake": …}, …}."""
    distractors = gen.phuong_an_nhieu[:]
    rnd.shuffle(distractors)
    options, explanations = {}, {}
    for letter in LETTERS:
        if letter == target:
            options[letter] = gen.noi_dung_dap_an_dung
            explanations[letter] = {"correct": True, "why": gen.giai_thich_dung}
        else:
            d = distractors.pop()
            options[letter] = d.noi_dung
            explanations[letter] = {"correct": False, "why": d.sai_vi, "mistake": d.nham_lan}
    return options, explanations, target


def least_used_letter(con: sqlite3.Connection) -> str:
    counts = {k: 0 for k in LETTERS}
    for r in con.execute("SELECT answer, count(*) AS n FROM mcq_items WHERE status != 'discarded' "
                         "GROUP BY answer"):
        counts[r["answer"]] = r["n"]
    return min(LETTERS, key=lambda k: (counts[k], k))


def clean_stem(stem: str, lead_in: str) -> str:
    """The vignette without the question: the model often repeats or paraphrases it at the end."""
    stem = stem.replace(lead_in, "").strip()
    sentences = re.split(r"(?<=[.!?:])\s+", stem)
    while sentences and sentences[-1].rstrip().endswith(("?", ":")):
        sentences.pop()
    return " ".join(sentences).strip()


def item_text(stem: str, lead_in: str, options: dict[str, str]) -> str:
    return f"{stem}\n\n{lead_in}\n" + "\n".join(f"{k}. {options[k]}" for k in LETTERS)


# --- the pipeline -------------------------------------------------------------------------

PROBLEM_HINTS = {
    "key_much_longer": "đáp án đúng dài/chi tiết hơn hẳn các phương án khác",
    "key_numbers_not_in_source": "đáp án có con số không có trong nguồn",
    "distractor_numbers_not_in_source": "phương án nhiễu có con số tự đặt, không lấy từ nguồn",
    "wrong_only_by_absence": "giải thích phương án nhiễu chỉ nói 'nguồn không đề cập' — phải nêu "
                             "điều nguồn nói khiến nó sai",
    "uncited": "giải thích thiếu trích dẫn [S#] hợp lệ",
    "not_single_best": "có hơn một phương án có thể đúng",
    "key_not_supported": "nguồn không khẳng định rõ đáp án đúng",
    "cueing": "câu hỏi có gợi ý làm lộ đáp án",
    "blind_answer": "thí sinh giỏi đọc nguồn vẫn chọn phương án khác",
    "bloom": "câu hỏi chỉ kiểm tra nhớ/hiểu, cần tình huống đòi hỏi áp dụng hoặc phân tích",
    "options_not_distinct": "các phương án trùng nhau",
    "all_none_of_the_above": "có phương án kiểu 'tất cả đều đúng/sai'",
    "no_vignette": "thiếu tình huống (tình huống trùng với câu hỏi)",
}


def _hint(problem: str) -> str:
    return next((h for k, h in PROBLEM_HINTS.items() if k in problem), problem)


def _validate(con: sqlite3.Connection, llm: Ollama, gen: Generated, chunks: list[sqlite3.Row],
              sources: str, rnd: random.Random) -> dict:
    """Letters, deterministic checks, blind answer and quality review for one draft."""
    options, expl, answer = assign_letters(gen, least_used_letter(con), rnd)
    stem = clean_stem(gen.tinh_huong, gen.cau_hoi)
    problems = [] if stem else ["no_vignette"]
    problems += check_item(options, answer, "\n".join(c["text"] for c in chunks),
                           {k: {"why": e["why"], "mistake": e.get("mistake")} for k, e in expl.items()},
                           len(chunks))
    out = {"options": options, "explanations": expl, "answer": answer, "stem": stem,
           "lead_in": gen.cau_hoi, "idea": gen.y_tuong, "bloom": None, "notes": ""}
    if not problems:
        question = item_text(stem, gen.cau_hoi, options)
        try:
            blind = llm.chat([{"role": "system", "content": BLIND_SYSTEM},
                              {"role": "user", "content": f"{sources}\n\n=====\n{question}"}],
                             schema=BlindAnswer, temperature=0)
            out["blind"] = blind.model_dump()
            if blind.dap_an != answer:
                problems.append(f"blind_answer_{blind.dap_an}")
            review = llm.chat([{"role": "system", "content": REVIEW_SYSTEM},
                               {"role": "user", "content": f"{sources}\n\n=====\n{question}\n\n"
                                f"Đáp án được đánh dấu: {answer}"}],
                              schema=QualityReview, temperature=0)
            out["review"] = review.model_dump()
            out["bloom"], out["notes"] = review.bloom, review.nhan_xet
            if not review.mot_dap_an_dung_nhat:
                problems.append("not_single_best")
            if not review.dap_an_dung_theo_nguon:
                problems.append("key_not_supported")
            if review.co_goi_y_lo_dap_an:
                problems.append("cueing")
            if review.bloom not in MCQ_ELIGIBLE:
                problems.append(f"bloom_{review.bloom}")
        except LLMError as e:
            problems.append(f"validator_error:{str(e).splitlines()[0][:80]}")
    out["problems"] = problems
    return out


def generate_item(con: sqlite3.Connection, llm: Ollama, target: Target, seed: int = 0,
                  bp: Blueprint | None = None, think: bool = False,
                  revisions: int = 1) -> tuple[int, str, list[str]]:
    """Generate, validate and store one item. Returns (item id, status, problems).

    A draft that fails gets up to `revisions` rewrites, with its problems and the reviewer's
    notes sent back to the writer; a rewrite is cheaper and more often fixable than a fresh
    draft. think=True lets the writer reason first: 1–2 min per draft and the reasoning can
    run away (`num_predict` caps it), so it is off by default."""
    bp = bp or load_blueprint()
    rnd = random.Random(f"{seed}:{target.chunk_id}")
    chunks = source_context(con, target.chunk_id)
    sources = sources_block(con, chunks)
    v = bp.van_de_by_id(target.van_de)
    mien_name = next(s.name for s in bp.mien_subs() if s.id == target.mien)
    bloom = target.bloom if target.bloom in MCQ_ELIGIBLE else "Áp dụng"
    ask = (f"{sources}\n\n=====\nMỤC TIÊU\n- Vấn đề: {v.id}. {v.name} — {v.description}\n"
           f"- Miền: {target.mien} {mien_name}\n- Mức Bloom: {bloom} — {BLOOM_TASK[bloom]}\n"
           "Viết 1 câu hỏi trắc nghiệm dựa chủ yếu vào [S1].")
    messages = [{"role": "system", "content": GEN_SYSTEM}, {"role": "user", "content": ask}]
    history = []
    for attempt in range(revisions + 1):
        try:
            gen = llm.chat(messages, schema=Generated, temperature=0.5, think=think,
                           options={"presence_penalty": 0, "num_predict": 6000})
        except LLMError as e:
            return 0, "error", [str(e).splitlines()[0]]
        result = _validate(con, llm, gen, chunks, sources, rnd)
        history.append(result["problems"])
        if not result["problems"] or attempt == revisions:
            break
        fixes = "\n".join(f"- {_hint(p)}" for p in dict.fromkeys(result["problems"]))
        messages += [{"role": "assistant", "content": gen.model_dump_json()},
                     {"role": "user", "content": f"Câu hỏi trên bị loại vì:\n{fixes}\n"
                      + (f"Nhận xét thẩm định: {result['notes']}\n" if result["notes"] else "")
                      + "Viết lại câu hỏi (cùng mục tiêu, cùng nguồn) khắc phục các lỗi này."}]
    problems = result["problems"]
    validation = {"target_bloom": bloom, "context": [c["chunk_id"] for c in chunks],
                  "idea": result["idea"], "problems": problems, "attempts": history,
                  **{k: result[k] for k in ("blind", "review") if k in result}}
    status = "discarded" if problems else "validated"
    with con:
        cur = con.execute(
            "INSERT INTO mcq_items (status, van_de, de_muc, mien, bloom, stem, lead_in, options, "
            "answer, explanations, sources, validation, model) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (status, target.van_de, target.de_muc, target.mien, result["bloom"] or bloom,
             result["stem"], result["lead_in"], json.dumps(result["options"], ensure_ascii=False),
             result["answer"], json.dumps(result["explanations"], ensure_ascii=False),
             json.dumps([{"chunk_id": c["chunk_id"], "content_hash": c["content_hash"]}
                         for c in chunks]),
             json.dumps(validation, ensure_ascii=False), settings.llm_model))
    return cur.lastrowid, status, problems
