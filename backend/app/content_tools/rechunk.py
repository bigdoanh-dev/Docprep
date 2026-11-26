"""Build reviewable corpus artifacts from original Word files."""
import csv
import hashlib
import io
import json
import re
import subprocess
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from .augment import augment
from .chunk import TARGET_MAX, chunk_doc
from .model import ParsedDoc
from .ocr_layout import Line, Word, format_scan, formatted_markdown
from .ocr_outline import OUTLINES, TOPICS
from .parse_docx import parse_docx
from .scans import extract_pages
from .sources import Source

VERSION = "yhdp-original-rechunk.v2"
MAX_DOCX = 120 * 1024**2
_PILOT_CAPTIONS = {
    "2dd6cec54376b05c8e7952306b4e232d3d81caa5694dcf4a6ba84b69366a70ad": "Bảng cân nặng chống sốc SXH dành cho nam",
    "ee1c03b60e73ef5db12a42a01b56067d5b9f46289b24528ddc30e1545ad0dadc": "Bảng cân nặng chống sốc SXH dành cho nữ",
}


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def registry(archive: Path) -> dict[str, Source]:
    with zipfile.ZipFile(archive) as package:
        info = package.getinfo("data/sources.yaml")
        if info.file_size > 256 * 1024:
            raise ValueError("Source registry too large")
        entries = yaml.safe_load(package.read(info))
    sources = [Source.model_validate(row) for row in entries]
    if len({s.doc_id for s in sources}) != len(sources) or any(
        not re.fullmatch(r"[a-z0-9_-]+", s.doc_id) for s in sources
    ):
        raise ValueError("Invalid or duplicate source ID")
    return {s.doc_id: s for s in sources}


def approx_tokens(text: str) -> int:
    # Local estimate. No model tokenizer or network access required.
    return len(re.findall(r"\w+|[^\w\s]", text)) * 2


def ocr_setup(tesseract, ocr_languages, tessdata=None):
    """Fail early when a requested language model is missing.

    Tesseract silently falls back to the remaining languages, so a missing vie.traineddata yields
    English-only OCR without diacritics. Returns the base command and a fingerprint of the models used.
    """
    command = [tesseract] + (["--tessdata-dir", str(tessdata)] if tessdata else [])
    listing = subprocess.run(command + ["--list-langs"], capture_output=True, encoding="utf-8",
                             errors="replace", timeout=60, check=False)
    output = listing.stdout + listing.stderr
    folder = re.search(r'languages in "([^"]+)"', output)
    available = {ln.strip() for ln in output.splitlines()[1:] if ln.strip()}
    wanted = [lang for lang in ocr_languages.split("+") if lang]
    if listing.returncode or not folder or (missing := [lang for lang in wanted if lang not in available]):
        raise ValueError(f"Tesseract language data missing: {', '.join(missing) if folder else output.strip()[:200]}."
                         " Pass --tessdata pointing at a folder with the .traineddata files.")
    digest = hashlib.sha256()
    for lang in wanted:
        digest.update(lang.encode() + b"\0" + (Path(folder.group(1)) / f"{lang}.traineddata").read_bytes())
    return command, digest.hexdigest()


def _ocr_tsv(source, page, assets, ocr, ocr_languages, cache):
    command, models = ocr
    image = assets / "pages" / page.file
    cached = None
    if cache:
        # Keyed by image bytes, languages and model files, so changing any of them OCRs the page again.
        key = hashlib.sha256(image.read_bytes() + b"\0" + ocr_languages.encode() + b"\0" + models.encode()).hexdigest()
        cached = Path(cache) / f"{key}.tsv"
        if cached.is_file():
            return cached.read_text(encoding="utf-8")
    result = subprocess.run(
        command + [str(image), "stdout", "-l", ocr_languages, "-c", "tessedit_create_tsv=1"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=180, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"OCR failed for {source.doc_id} image page {page.index}: {result.stderr.strip()[:300]}")
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def _scan_page(source, page, assets, ocr, ocr_languages, cache=None):
    if page.blank:
        return [], {"page": page.index, "status": "blank"}
    stdout = _ocr_tsv(source, page, assets, ocr, ocr_languages, cache)
    lines, confidences = {}, []
    tsv = csv.DictReader(io.StringIO(stdout.lstrip("\ufeff")), delimiter="\t", quoting=csv.QUOTE_NONE)
    fields = {"level", "text", "conf", "block_num", "par_num", "line_num", "left", "top", "width", "height"}
    if not tsv.fieldnames or not fields <= set(tsv.fieldnames):
        raise RuntimeError(f"OCR returned invalid TSV for {source.doc_id} image page {page.index}")
    for row in tsv:
        word = (row.get("text") or "").strip()
        if row["level"] != "5" or not word:
            continue
        key = tuple(row[k] for k in ("block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(
            Word(word, *(int(row[field]) for field in ("left", "top", "width", "height")))
        )
        confidences.append(float(row["conf"]))
    confidence = round(sum(confidences) / len(confidences), 1) if confidences else None
    if not lines:
        return [], {"page": page.index, "status": "unreadable", "confidence": confidence}
    return [Line(key[:2], tuple(words)) for key, words in lines.items()], {
        "page": page.index, "width": page.width, "status": "text", "confidence": confidence,
    }


def _build_scan(source, path, assets, tesseract, ocr_languages, workers, outline, topics=None, cache=None,
                tessdata=None):
    ocr = ocr_setup(tesseract, ocr_languages, tessdata)
    pages = extract_pages(path, assets / "pages")
    if not pages:
        raise ValueError(f"{source.doc_id}: no image pages in scanned Word document")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        result = list(pool.map(lambda page: _scan_page(source, page, assets, ocr, ocr_languages, cache), pages))
    blocks = format_scan(result, source.strip_patterns, outline, topics)
    return ParsedDoc(doc_id=source.doc_id, blocks=blocks), [status for _, status in result]


def _word_captions(parsed, assets):
    for block in parsed.blocks:
        if parsed.doc_id == "qd2760" and block.loc.anchor == "pl9/2" and block.figure_path:
            digest = hashlib.sha256((assets / block.figure_path).read_bytes()).hexdigest()
            caption = _PILOT_CAPTIONS.get(digest)
            if caption:
                block.caption = caption
                block.text = f"[Hình: {caption}]"


def _split_long_text(parsed):
    blocks = []
    for block in parsed.blocks:
        if block.kind not in {"para", "list"} or approx_tokens(block.text) <= TARGET_MAX or "table_flattened" in block.needs_review:
            blocks.append(block)
            continue
        units = re.split(r"\n+|(?<=[.!?;])\s+(?=[A-ZÀ-Ỹ])", block.text)
        # Preserve an indivisible sentence/list line and flag it for review rather than cutting it mid-idea.
        for unit in filter(str.strip, units):
            flags = list(block.needs_review)
            if approx_tokens(unit) > TARGET_MAX:
                flags.append("oversize_text_requires_review")
            blocks.append(block.model_copy(update={"text": unit, "needs_review": flags}))
    return parsed.model_copy(update={"blocks": blocks})


def build(source, path, output, *, tesseract=None, ocr_languages="vie+eng", workers=4, ocr_cache=None,
          tessdata=None):
    path, output = Path(path), Path(output)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_DOCX:
        raise ValueError(f"{source.doc_id}: Word file missing, empty or too large")
    if not 1 <= workers <= 16:
        raise ValueError("OCR workers must be in 1..16")
    if source.format == "scan" and not tesseract:
        raise ValueError(f"{source.doc_id}: Tesseract with Vietnamese data required")
    with zipfile.ZipFile(path) as original:
        if sum(entry.file_size for entry in original.infolist()) > 512 * 1024**2:
            raise ValueError(f"{source.doc_id}: expanded Word file exceeds limit")
    output.mkdir(parents=True, exist_ok=False)
    assets = output / "assets"
    assets.mkdir()
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if source.format == "scan":
        parsed, page_report = _build_scan(source, path, assets, tesseract, ocr_languages, workers,
                                          OUTLINES.get(source_hash), TOPICS.get(source_hash), ocr_cache, tessdata)
        (output / "formatted.md").write_text(formatted_markdown(parsed.blocks), encoding="utf-8")
    else:
        parsed, page_report = parse_docx(path, source, assets / "figures"), []
        _word_captions(parsed, assets)
    chunks = chunk_doc(_split_long_text(parsed), source, approx_tokens, preserve_limit=True)
    if not chunks:
        raise ValueError(f"{source.doc_id}: zero chunks, inspect parser/OCR")
    records = augment(chunks, source.title)
    parents = {}
    context_children = {}
    for r in records:
        loc, metadata = r["location"], r["location"]["augmentation"]
        parent = parents.setdefault(metadata["parent_id"], {"section_path": loc["section_path"], "child_ids": []})
        parent["child_ids"].append(r["chunk_id"])
        if r["kind"] == "table" and (sibling := context_children.get(metadata["parent_id"])):
            metadata["context_child_id"] = sibling
        if r["kind"] == "text" and len(r["text"]) <= 1800:
            # Only a preceding text sibling in the same section is eligible as supporting context.
            context_children[metadata["parent_id"]] = r["chunk_id"]
    parsed.save(output / "parsed.json")
    write_json(output / "parents.json", parents)
    (output / "chunks.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    report = {
        "pipeline": VERSION, "source": source.model_dump(), "source_sha256": source_hash,
        "chunks": len(records), "kinds": dict(Counter(r["kind"] for r in records)),
        "parents": len(parents), "question_drafts": sum(bool(r["location"]["augmentation"]["questions"]) for r in records),
        "quality_flags": dict(Counter(f for r in records for f in r["needs_review"])),
        "scan_pages": page_report, "printed_page_verified_chunks": sum(bool(r["location"]["printed_pages"]) for r in records),
        "heading_blocks": sum(b.kind == "heading" for b in parsed.blocks),
        "state": "review_required",
    }
    write_json(output / "report.json", report)
    return report, records
