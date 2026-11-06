"""Chunk tagger (P0 T15, design §4.3): vấn đề, miền, Bloom ceiling, content type, population.

Each chunk is tagged twice: greedily (temperature 0, the stored tag) and sampled (temperature
0.6, a disagreement probe). `route()` sends it to the review queue when the runs disagree, a confidence is low, or the chunk carries a needs_review flag. Human tags are
pinned by (chunk_id, content_hash) and never overwritten.
"""

import json
import random
import sqlite3
from functools import cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from yhdp.blueprint import Blueprint, load_blueprint
from yhdp.ingest.model import Loc
from yhdp.llm import Ollama
from yhdp.settings import settings
from yhdp.sources import Source

BLOOM = ("Nhớ", "Hiểu", "Áp dụng", "Phân tích", "Đánh giá")
MCQ_ELIGIBLE = {"Áp dụng", "Phân tích", "Đánh giá"}
CONTENT_TYPES = ("định_nghĩa", "dịch_tễ", "nguyên_nhân", "lâm_sàng", "cận_lâm_sàng", "chẩn_đoán",
                 "chẩn_đoán_phân_biệt", "điều_trị", "phòng_bệnh", "tiên_lượng", "quy_trình", "khác")
POPULATIONS = ("trẻ_em", "thiếu_niên", "người_lớn", "thai_phụ", "người_cao_tuổi", "cộng_đồng")
TEMPERATURES = (0.0, 0.6)  # run 1 is the tag of record; run 2 only probes for disagreement
MAX_CHUNK_CHARS = 6000  # ~1,500 tokens; the longest tables are cut, the rest pass whole

BloomLevel = Literal[BLOOM]
ContentType = Literal[CONTENT_TYPES]
Population = Literal[POPULATIONS]


def van_de_label(v) -> str:
    return f"{v.id}. {v.name}"


def mien_label(s) -> str:
    return f"{s.id} {s.name}"


@cache
def output_schema(bp: Blueprint | None = None) -> type[BaseModel]:
    """LLM output model with blueprint labels ("21. Sốt", "3.2 Điều trị bằng thuốc") as enums:
    decoding can't invent one, and the model writes the name rather than a bare number it
    can mix up. `from_llm()` turns labels back into ids."""
    bp = bp or load_blueprint()
    VanDeLabel = Literal[tuple(van_de_label(v) for v in bp.van_de)]
    MienLabel = Literal[tuple(mien_label(s) for s in bp.mien_subs())]

    class VanDeTag(BaseModel):
        id: VanDeLabel
        conf: float = Field(ge=0, le=1)

    class MienTag(BaseModel):
        id: MienLabel
        conf: float = Field(ge=0, le=1)

    class BloomTag(BaseModel):
        level: BloomLevel
        conf: float = Field(ge=0, le=1)

    class TagOutput(BaseModel):
        ly_do: str  # first, so the model states what the chunk is about before choosing
        van_de_chinh: VanDeTag  # exactly one primary, by construction
        van_de_phu: list[VanDeTag] = Field(max_length=2)
        mien: list[MienTag] = Field(min_length=1, max_length=2)
        bloom_ceiling: BloomTag
        content_type: ContentType
        population: list[Population] = Field(max_length=3)

        @model_validator(mode="after")
        def _distinct(self):
            ids = [self.van_de_chinh.id, *(v.id for v in self.van_de_phu)]
            if len(set(ids)) != len(ids):
                raise ValueError("van_de_phu không được lặp lại van_de_chinh hoặc lặp nhau")
            return self

    return TagOutput


# --- prompt ------------------------------------------------------------------------------

RUBRIC = """\
## Chọn vấn đề primary (bản nháp, chờ bác sĩ duyệt)
- Chọn theo NHIỆM VỤ của đoạn, không chỉ theo tên bệnh. Đoạn về chẩn đoán, điều trị, theo dõi \
một ca bệnh → vấn đề lâm sàng (đề mục 2, 4, 6…). Vấn đề cộng đồng của đề mục 1 (giám sát, khai báo, \
phòng chống dịch, sàng lọc) chỉ là primary khi đoạn thật sự nói về các hoạt động đó.
- Khi bệnh khớp nhiều vấn đề lâm sàng, ưu tiên vấn đề có mô tả nhắc đích danh bệnh đó \
(VD: SXHD → 22 Sốt và phát ban; viêm màng não → 23; tiêu chảy do vi khuẩn → 26; THA → 39).
- van_de_phu chỉ ghi vấn đề mà đoạn thật sự phục vụ; để trống [] còn hơn ghi cho đủ.

## Chọn miền (mien)
- 2.1: hỏi bệnh, thăm khám, theo dõi dấu hiệu lâm sàng. 2.2: xét nghiệm, đo đạc, kỹ thuật cận lâm sàng.
- 2.3: tiêu chuẩn chẩn đoán, phân độ, chẩn đoán phân biệt. 2.4: biến chứng, tiên lượng, kết cục.
- 3.1: phòng bệnh, dinh dưỡng, lối sống, tiêm chủng, giáo dục sức khỏe.
- 3.2: chọn thuốc, liều, đường dùng, thời gian dùng, tương tác/chống chỉ định thuốc.
- 3.3: thủ thuật, chăm sóc điều dưỡng, bù dịch, thở oxy và các can thiệp không phải chọn thuốc.
- 3.4: theo dõi điều trị, điều chỉnh phác đồ, chuyển tuyến, quản lý lâu dài.
- 4.1–4.3: chỉ khi đoạn nói về tư vấn/hướng dẫn người bệnh, người nhà, đồng nghiệp, liên ngành.

## Mức Bloom trần (bloom_ceiling)
Bloom mô tả nhiệm vụ học tập, không mô tả văn bản. Hãy gắn MỨC CAO NHẤT mà một câu hỏi trắc nghiệm \
tình huống viết từ đoạn này có thể đạt được (đề thi chỉ gồm Áp dụng, Phân tích, Đánh giá):
- Nhớ: định nghĩa, tên gọi, con số đơn lẻ cần thuộc, danh mục.
  VD: "Virus Dengue có 4 típ huyết thanh DEN-1 đến DEN-4."; danh mục chữ viết tắt.
- Hiểu: giải thích cơ chế, diễn biến, ý nghĩa; mô tả không kèm tiêu chuẩn hay ngưỡng hành động.
  VD: "Giai đoạn nguy hiểm do tăng tính thấm thành mạch gây thoát huyết tương."; mô tả đặc điểm dịch tễ.
- Áp dụng: tiêu chuẩn, ngưỡng, phân độ, phác đồ, liều, quy trình từng bước — dùng để xử lý một tình huống cụ thể.
  VD: bảng phân độ THA theo trị số HA; "Truyền Ringer lactat 6–7 ml/kg/giờ trong 1–3 giờ".
- Phân tích: chẩn đoán phân biệt, diễn giải xét nghiệm/dữ liệu, suy luận nguyên nhân, đọc số liệu dịch tễ.
  VD: phân biệt viêm não HSV với viêm não Nhật Bản, áp xe não; diễn giải Hct tăng kèm tiểu cầu giảm nhanh.
- Đánh giá: cân nhắc lựa chọn giữa các phương án, chỉ định và chống chỉ định, khi nào đổi chiến lược hoặc chuyển tuyến.
  VD: khi nào chuyển từ Ringer lactat sang dung dịch cao phân tử; tiêu chuẩn chuyển tuyến THA từ trạm y tế xã.
Hiệu chỉnh:
- Danh mục thuốc/biệt dược, danh sách biến chứng, bảng chú thích chữ viết tắt, câu dẫn chiếu ("Xem …"), \
nguyên tắc chung chung → Nhớ hoặc Hiểu, kể cả khi nói về điều trị.
- Áp dụng cần có tiêu chuẩn, ngưỡng, liều hoặc bước làm cụ thể để giải quyết một tình huống.
- Đánh giá cần có điểm quyết định rõ ràng trong đoạn (đổi thuốc, giảm bậc, chuyển tuyến, cho về).
- Chỉ có tiêu đề hình: suy luận theo loại sơ đồ (sơ đồ xử trí/phân nhóm điều trị → Áp dụng).

## Loại nội dung (content_type)
định_nghĩa · dịch_tễ · nguyên_nhân · lâm_sàng · cận_lâm_sàng · chẩn_đoán · chẩn_đoán_phân_biệt · \
điều_trị · phòng_bệnh · tiên_lượng · quy_trình · khác

## Đối tượng (population)
trẻ_em · thiếu_niên · người_lớn · thai_phụ · người_cao_tuổi · cộng_đồng. Lấy theo VỊ TRÍ và nội \
dung: mục "TRẺ EM (< 16 TUỔI)" → chỉ trẻ_em (thêm thiếu_niên nếu nói 13–16 tuổi), không thêm \
người_lớn. Để trống [] nếu cả vị trí lẫn nội dung không nêu riêng đối tượng nào.

## Độ tin cậy (conf)
0–1, thật sự hiệu chỉnh: 0.9+ chỉ khi đoạn văn rõ ràng thuộc nhãn đó; 0.5–0.7 khi phải đoán \
(đoạn quá ngắn, chỉ có tiêu đề, hoặc nằm giữa hai vấn đề)."""


def system_prompt(bp: Blueprint | None = None) -> str:
    bp = bp or load_blueprint()
    de_muc = {d.id: d.name for d in bp.de_muc}
    van_de_lines, current = [], None
    for v in bp.van_de:
        if v.de_muc != current:
            current = v.de_muc
            van_de_lines.append(f"### Đề mục {v.de_muc}: {de_muc[v.de_muc]}")
        van_de_lines.append(f"{v.id}. {v.name} — {v.description}")
    mien_lines = [f"{s.id} {s.name}" for s in bp.mien_subs()]
    return f"""Bạn gắn nhãn các đoạn trích tài liệu y khoa theo cấu trúc đề thi NLHN Bác sĩ Y học \
dự phòng ({bp.source}). Trả về JSON đúng schema, không thêm chữ nào khác.

## Vấn đề: van_de_chinh = vấn đề mà đoạn này phục vụ nhiều nhất; van_de_phu = 0–2 vấn đề khác
{chr(10).join(van_de_lines)}

## Miền năng lực (mien): chọn 1–2 tiểu mục mà câu hỏi từ đoạn này sẽ kiểm tra
{chr(10).join(mien_lines)}

{RUBRIC}

## ly_do
Một hoặc hai câu: đoạn này nói về gì, vì sao chọn vấn đề primary và mức Bloom đó."""


def user_prompt(chunk: dict, source: Source, bp: Blueprint | None = None) -> str:
    bp = bp or load_blueprint()
    loc = Loc.model_validate_json(chunk["loc"]) if isinstance(chunk["loc"], str) else chunk["loc"]
    prior = ", ".join(f"{i}. {bp.van_de_by_id(i).name}" for i in source.van_de_prior) or "không có"
    text = chunk["text"]
    if len(text) > MAX_CHUNK_CHARS:
        text = text[:MAX_CHUNK_CHARS] + "\n…(đã cắt bớt)"
    kind = {"table": "bảng", "figure": "hình (chỉ có tiêu đề)", "box": "hộp", "formula": "công thức",
            "text": "văn bản"}[chunk["kind"]]
    return (f"TÀI LIỆU: {source.title} ({source.issuer or 'không rõ'}; {source.kind})\n"
            f"Vấn đề thường gặp trong tài liệu này (chỉ là gợi ý): {prior}\n"
            f"VỊ TRÍ: {' › '.join(loc.section_path)}\n"
            f"LOẠI: {kind}\n\nNỘI DUNG:\n{text}")


# --- routing -----------------------------------------------------------------------------

def primary_van_de(out: dict) -> int:
    return next(v["id"] for v in out["van_de"] if v["primary"])


def top_mien(out: dict) -> str:
    return max(out["mien"], key=lambda m: m["conf"])["id"]


def from_llm(out: dict) -> dict:
    """LLM output (labels, van_de_chinh/van_de_phu) → internal shape: ids (21, "3.2") and one
    van_de list with a primary flag."""
    out = dict(out)
    main, others = out.pop("van_de_chinh"), out.pop("van_de_phu")
    van_de = [{"id": int(v["id"].split(".", 1)[0]), "primary": i == 0, "conf": v["conf"]}
              for i, v in enumerate([main, *others])]
    return {**out, "van_de": van_de,
            "mien": [{**m, "id": m["id"].split(" ", 1)[0]} for m in out["mien"]]}


def to_llm(out: dict, bp: Blueprint | None = None) -> dict:
    """Inverse of from_llm, for few-shot examples."""
    bp = bp or load_blueprint()
    subs = {s.id: s for s in bp.mien_subs()}
    out = dict(out)
    van_de = sorted(out.pop("van_de"), key=lambda v: not v["primary"])
    labelled = [{"id": van_de_label(bp.van_de_by_id(v["id"])), "conf": v["conf"]} for v in van_de]
    return {"ly_do": out.pop("ly_do", ""), "van_de_chinh": labelled[0], "van_de_phu": labelled[1:],
            **out, "mien": [{**m, "id": mien_label(subs[m["id"]])} for m in out["mien"]]}


def mien_agree(run1: dict, run2: dict) -> bool:
    """Each run's top miền is among the other run's picks (order swaps of 2.3/3.3 agree)."""
    ids1, ids2 = {m["id"] for m in run1["mien"]}, {m["id"] for m in run2["mien"]}
    return top_mien(run1) in ids2 and top_mien(run2) in ids1


def bloom_agree(run1: dict, run2: dict) -> bool:
    """Same level, or neighbours on the same side of the MCQ cut-off (Áp dụng vs Phân tích)."""
    a, b = run1["bloom_ceiling"]["level"], run2["bloom_ceiling"]["level"]
    return a == b or (abs(BLOOM.index(a) - BLOOM.index(b)) == 1
                      and (a in MCQ_ELIGIBLE) == (b in MCQ_ELIGIBLE))


def route(run1: dict, run2: dict, flags: list[str],
          conf_min: float | None = None) -> tuple[str, list[str]]:
    """('auto' | 'review', reasons). Runs are TagOutput dicts with ids (see from_llm)."""
    conf_min = settings.tag_conf_min if conf_min is None else conf_min
    reasons = []
    if primary_van_de(run1) != primary_van_de(run2):
        reasons.append("van_de_disagree")
    if not mien_agree(run1, run2):
        reasons.append("mien_disagree")
    if not bloom_agree(run1, run2):
        reasons.append("bloom_disagree")
    for run in (run1, run2):
        confs = [next(v["conf"] for v in run["van_de"] if v["primary"]),
                 max(m["conf"] for m in run["mien"]), run["bloom_ceiling"]["conf"]]
        if min(confs) < conf_min:
            reasons.append("low_conf")
            break
    reasons += [f"flag:{f}" for f in flags]
    return ("review" if reasons else "auto"), reasons


# --- records -----------------------------------------------------------------------------

def to_record(chunk: dict, doc: sqlite3.Row, out: dict, status: str,
              bp: Blueprint | None = None) -> dict:
    """Design §4.3 tag record; `source` comes from the chunk, never from the LLM."""
    bp = bp or load_blueprint()
    loc = json.loads(chunk["loc"])
    mien_names = {s.id: s.name for s in bp.mien_subs()}
    van_de = sorted(out["van_de"], key=lambda v: (not v["primary"], -v["conf"]))
    return {
        "chunk_id": chunk["chunk_id"],
        "source": {"doc_id": doc["doc_id"], "doc_title": doc["title"], "issuer": doc["issuer"],
                   "year": doc["year"], "source_kind": doc["kind"],
                   "section_path": loc["section_path"], "printed_pages": loc.get("printed_pages"),
                   "image_indices": loc.get("image_indices")},
        "blueprint": {
            "van_de": van_de,
            "de_muc": list(dict.fromkeys(bp.van_de_by_id(v["id"]).de_muc for v in van_de)),
            "mien": [{**m, "label": mien_names[m["id"]]} for m in out["mien"]]},
        "bloom_ceiling": out["bloom_ceiling"],
        "mcq_eligible": out["bloom_ceiling"]["level"] in MCQ_ELIGIBLE,
        "content_type": out["content_type"],
        "population": out["population"],
        "ly_do": out.get("ly_do", ""),
        "review_status": status,
    }


def record_to_output(record: dict) -> dict:
    """A (human) tag record back in output shape (ids), for few-shot examples via to_llm()."""
    return {"ly_do": record.get("ly_do", ""),
            "van_de": [{k: v[k] for k in ("id", "primary", "conf")} for v in record["blueprint"]["van_de"]],
            "mien": [{"id": m["id"], "conf": m["conf"]} for m in record["blueprint"]["mien"]],
            "bloom_ceiling": record["bloom_ceiling"], "content_type": record["content_type"],
            "population": record["population"]}


# --- running -----------------------------------------------------------------------------

def few_shots(con: sqlite3.Connection, doc_id: str, source: Source, n: int = 8) -> list[dict]:
    rows = con.execute(
        "SELECT c.*, t.tags FROM chunk_tags t JOIN chunks c ON c.chunk_id = t.chunk_id "
        "AND c.content_hash = t.content_hash WHERE t.source = 'human' "
        "ORDER BY (c.doc_id = ?) DESC, t.ts DESC LIMIT ?", (doc_id, n)).fetchall()
    messages = []
    for r in rows:
        src = source if r["doc_id"] == doc_id else _source(r["doc_id"])
        messages += [{"role": "user", "content": user_prompt(dict(r), src)},
                     {"role": "assistant",
                      "content": json.dumps(to_llm(record_to_output(json.loads(r["tags"]))),
                                            ensure_ascii=False)}]
    return messages


def _source(doc_id: str) -> Source:
    from yhdp.sources import load_sources

    return load_sources()[doc_id]


def pilot_ids(con: sqlite3.Connection) -> list[str]:
    """The pilot sample, frozen on first use so prompt changes are compared on the same chunks."""
    path = settings.derived_dir / "tag_pilot_ids.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    ids = select_pilot(con)
    path.write_text(json.dumps(ids, indent=1), encoding="utf-8")
    return ids


def select_pilot(con: sqlite3.Connection, per_doc: int = 10, seed: int = 0) -> list[str]:
    """Per doc: up to 3 tables, 2 figures, the rest text — a fixed, reproducible sample."""
    rnd = random.Random(seed)
    picked = []
    for (doc_id,) in con.execute("SELECT DISTINCT doc_id FROM chunks ORDER BY doc_id"):
        by_kind: dict[str, list[str]] = {}
        for r in con.execute("SELECT chunk_id, kind FROM chunks WHERE doc_id = ? ORDER BY seq",
                             (doc_id,)):
            by_kind.setdefault(r["kind"], []).append(r["chunk_id"])
        take = []
        for kind, n in (("table", 3), ("figure", 2)):
            pool = by_kind.get(kind, [])
            take += rnd.sample(pool, min(n, len(pool)))
        rest = [c for k, ids in by_kind.items() if k not in ("table", "figure") for c in ids]
        take += rnd.sample(rest, min(per_doc - len(take), len(rest)))
        picked += take
    return picked


def pending(con: sqlite3.Connection, chunk_ids: list[str] | None = None,
            force: bool = False) -> list[sqlite3.Row]:
    """Chunks needing a tag: no human tag for this content, and no auto tag unless force."""
    rows = con.execute(
        "SELECT c.* FROM chunks c WHERE NOT EXISTS (SELECT 1 FROM chunk_tags t WHERE "
        "t.chunk_id = c.chunk_id AND t.content_hash = c.content_hash AND (t.source = 'human' "
        "OR (t.source = 'auto' AND NOT ?))) ORDER BY c.doc_id, c.seq", (force,)).fetchall()
    if chunk_ids is not None:
        wanted = set(chunk_ids)
        rows = [r for r in rows if r["chunk_id"] in wanted]
    return rows


def queue_audit(con: sqlite3.Connection, n: int = 30, seed: int = 0) -> int:
    """Queue a random sample of unqueued auto-tagged chunks, so the eval also sees chunks the
    model was confident about (not only the hard ones)."""
    rows = con.execute(
        "SELECT c.chunk_id, c.content_hash FROM chunks c JOIN chunk_tags t ON t.chunk_id = c.chunk_id "
        "AND t.content_hash = c.content_hash AND t.source = 'auto' "
        "WHERE NOT EXISTS (SELECT 1 FROM review_items r WHERE r.kind = 'tag' AND r.ref = c.chunk_id) "
        "AND NOT EXISTS (SELECT 1 FROM chunk_tags h WHERE h.chunk_id = c.chunk_id "
        "AND h.content_hash = c.content_hash AND h.source = 'human') ORDER BY c.chunk_id").fetchall()
    sample = random.Random(seed).sample(rows, min(n, len(rows)))
    with con:
        con.executemany(
            "INSERT INTO review_items (kind, ref, payload) VALUES ('tag', ?, ?)",
            [(r["chunk_id"], json.dumps({"content_hash": r["content_hash"], "runs": None,
                                         "reasons": ["audit_sample"], "old_human": None}))
             for r in sample])
    return len(sample)


def tag_chunk(con: sqlite3.Connection, llm: Ollama, chunk: sqlite3.Row, source: Source,
              system: str) -> tuple[str, list[str]]:
    if con.execute("SELECT 1 FROM chunk_tags WHERE chunk_id = ? AND content_hash = ? "
                   "AND source = 'human'", (chunk["chunk_id"], chunk["content_hash"])).fetchone():
        return "skipped", ["human_tagged"]  # reviewed while this run was going
    schema = output_schema()
    messages = [{"role": "system", "content": system}, *few_shots(con, chunk["doc_id"], source),
                {"role": "user", "content": user_prompt(dict(chunk), source)}]
    runs = [from_llm(llm.chat(messages, schema=schema, temperature=t,
                              options={"presence_penalty": 0}).model_dump()) for t in TEMPERATURES]
    flags = list(json.loads(chunk["extra"]).get("needs_review", []))
    if chunk["kind"] == "figure" and "\n" not in chunk["text"]:
        flags.append("figure_undescribed")  # only a title until T11 adds a description
    status, reasons = route(runs[0], runs[1], flags)
    old_human = con.execute(
        "SELECT tags FROM chunk_tags WHERE chunk_id = ? AND source = 'human' "
        "AND content_hash != ? ORDER BY ts DESC LIMIT 1",
        (chunk["chunk_id"], chunk["content_hash"])).fetchone()
    if old_human:
        status, reasons = "review", [*reasons, "content_changed"]
    doc = con.execute("SELECT * FROM documents WHERE doc_id = ?", (chunk["doc_id"],)).fetchone()
    record = to_record(dict(chunk), doc, runs[0], status)
    with con:
        con.execute(
            "INSERT INTO chunk_tags (chunk_id, content_hash, tags, source) VALUES (?, ?, ?, 'auto') "
            "ON CONFLICT (chunk_id, content_hash, source) DO UPDATE SET tags = excluded.tags, "
            "ts = datetime('now')",
            (chunk["chunk_id"], chunk["content_hash"], json.dumps(record, ensure_ascii=False)))
        if status == "review":
            payload = {"content_hash": chunk["content_hash"], "runs": runs, "reasons": reasons,
                       "old_human": json.loads(old_human["tags"]) if old_human else None}
            con.execute(
                "INSERT INTO review_items (kind, ref, payload) VALUES ('tag', ?, ?) "
                "ON CONFLICT (kind, ref) DO UPDATE SET payload = excluded.payload, "
                "status = 'open', ts = datetime('now')",
                (chunk["chunk_id"], json.dumps(payload, ensure_ascii=False)))
        else:
            con.execute("DELETE FROM review_items WHERE kind = 'tag' AND ref = ? AND status = 'open'",
                        (chunk["chunk_id"],))
    return status, reasons
