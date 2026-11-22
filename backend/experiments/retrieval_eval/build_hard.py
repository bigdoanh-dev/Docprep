"""Adds HARD in-scope questions to the silver set: the way students actually type, not the guideline's words.

Same method as build_set.py (one passage -> one question, TREC-style pooling, the model labels, the
source passage must be confirmed), with two differences:
- passages already used by silver_set.jsonl are skipped, so the two sets do not overlap;
- each question is written in one of five student styles that make lexical search harder:
  abbreviations, no diacritics, synonyms or lay / English terms, a few search keywords, and an
  indirect question through a consequence or situation.

The result is written to hard_set.jsonl (scored with run_eval.py / rerank_eval.py --set hard_set.jsonl).
It tells whether tokenisation, phrase queries or synonyms are worth building: if the hybrid top 30
still holds the right passage for these, the reranker already covers them.
"""
import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.chat.postcheck import _squash
from app.db import connect
from build_set import candidates, judge, sample
from common import ask_json, gateway, seeded, visible_passages

HERE = Path(__file__).resolve().parent
STYLES = {
    "viet_tat": "dùng từ viết tắt sinh viên y hay gõ (ví dụ SXH, SXHD, NKH, HA, THA, BN, XN, KS, TCM, ĐTĐ, TE) cho tên bệnh, "
                "xét nghiệm hoặc thuốc trong câu hỏi; vẫn có dấu",
    "khong_dau": "gõ tiếng Việt KHÔNG DẤU như khi gõ vội trên điện thoại (ví dụ 'lieu dopamin trong soc sot xuat huyet o tre'); "
                 "có thể viết tắt",
    "dong_nghia": "thay các từ chính của đoạn bằng từ đồng nghĩa, từ thông thường hoặc thuật ngữ tiếng Anh sinh viên hay dùng "
                  "(ví dụ 'sepsis' thay 'nhiễm khuẩn huyết', 'ỉa chảy' thay 'tiêu chảy', 'truyền dịch' thay 'bù dịch')",
    "tu_khoa": "chỉ gõ 3 đến 8 từ khoá như ô tìm kiếm, không thành câu (ví dụ 'tiêu chuẩn nhập viện tay chân miệng')",
    "gian_tiep": "hỏi gián tiếp qua hậu quả, mục đích hoặc tình huống chung, không nhắc tên mục hay cụm từ đặc trưng của đoạn "
                 "(ví dụ 'khi nào phải chuyển người bệnh lên tuyến trên' thay vì hỏi 'tiêu chuẩn chuyển viện')",
}
QUESTION_SYSTEM = """You write realistic search queries for Vietnamese preventive-medicine students, to stress-test a search engine.
Given one passage from a Vietnamese clinical guideline and a typing style, write ONE query in Vietnamese that a student would type into a study chatbot, in that style, such that this passage answers it.

Rules
- The passage alone must answer it. Ask about something the passage actually states.
- Follow the style exactly. Do not copy distinctive phrases from the passage.
- The query must still be clear enough that a tutor knows which disease or topic it is about.
- Never ask about one specific patient (no "con tôi", "bệnh nhân này", no dose for a person). Never refer to "đoạn văn", "tài liệu", "bảng trên".
- Under 30 words.
Output JSON only: {"question": "...", "answer_quote": "<words copied exactly from the passage that answer it>"}"""


def write_question(gw, p: dict, style: str) -> dict | None:
    user = (f"Kiểu gõ: {STYLES[style]}.\n\nVị trí: {p['document']} › {p['context'] or p['chapter'] or ''}\n\nĐoạn:\n{p['text']}")
    data = ask_json(gw, QUESTION_SYSTEM, user, "eval-hard-question-v1")
    if not data or not isinstance(data.get("question"), str) or not isinstance(data.get("answer_quote"), str):
        return None
    if len(data["answer_quote"].split()) < 2 or _squash(data["answer_quote"]) not in _squash(p["text"]):
        return None
    return {"question": data["question"].strip(), "answer_quote": data["answer_quote"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=55, help="passages to write questions from (some are filtered out)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--exclude", default=str(HERE / "silver_set.jsonl"))
    ap.add_argument("--out", default=str(HERE / "hard_set.jsonl"))
    args = ap.parse_args()
    rng, gw = seeded(20261123), gateway()
    used = {json.loads(l).get("source") for l in Path(args.exclude).read_text(encoding="utf-8").splitlines() if l.strip()}

    with connect() as conn:
        passages = [p for p in visible_passages(conn) if p["id"] not in used]
    picked = sample(passages, args.n, rng)
    styles = list(STYLES)
    print(f"{len(passages)} unused passages; {len(picked)} sampled")

    with ThreadPoolExecutor(args.workers) as pool:
        written = list(pool.map(lambda ip: write_question(gw, ip[1], styles[ip[0] % len(styles)]), enumerate(picked)))
    items = [{"type": "in_scope", "style": styles[i % len(styles)], "source": p["id"], "document": p["document"],
              "chapter": p["chapter"], **w} for i, (p, w) in enumerate(zip(picked, written)) if w]
    print(f"{len(items)} questions written")

    with connect() as conn:
        for it in items:
            it["_cands"] = candidates(conn, gw, it["question"], it["source"])
            rng.shuffle(it["_cands"])
    with ThreadPoolExecutor(args.workers) as pool:
        labels = list(pool.map(lambda it: judge(gw, it["question"], it["_cands"]), items))

    kept, dropped = [], defaultdict(int)
    for it, lab in zip(items, labels):
        pool_size = len(it.pop("_cands"))
        if lab is None:
            dropped["judge_failed"] += 1; continue
        if it["source"] not in lab["answers"]:
            dropped["source_not_confirmed"] += 1; continue
        kept.append({**it, "gold": lab["answers"], "partial": lab["partial"], "pool": pool_size})
    for n, it in enumerate(kept, 1):
        it["id"] = f"HARD-{n:03d}"
    Path(args.out).write_text("\n".join(json.dumps(k, ensure_ascii=False) for k in kept) + "\n", encoding="utf-8")
    by_style = defaultdict(int)
    for k in kept:
        by_style[k["style"]] += 1
    print(f"kept {len(kept)} {dict(by_style)}; dropped {dict(dropped)} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
