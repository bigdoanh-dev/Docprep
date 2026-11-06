import typer

from yhdp.blueprint import load_blueprint
from yhdp.settings import settings
from yhdp.sources import load_sources

app = typer.Typer(help="YHDP Graph RAG study assistant", no_args_is_help=True)
ingest = typer.Typer(help="Ingestion pipeline stages", no_args_is_help=True)
app.add_typer(ingest, name="ingest")
dictionary = typer.Typer(help="Medical synonym dictionary", no_args_is_help=True)
app.add_typer(dictionary, name="dict")
tag = typer.Typer(help="Chunk tagging (vấn đề, miền, Bloom)", no_args_is_help=True)
app.add_typer(tag, name="tag")
mcq = typer.Typer(help="MCQ generator and item bank", no_args_is_help=True)
app.add_typer(mcq, name="mcq")
report = typer.Typer(help="Coverage and evaluation reports", no_args_is_help=True)
app.add_typer(report, name="report")
user = typer.Typer(help="Web app accounts", no_args_is_help=True)
app.add_typer(user, name="user")


def _doc_ids(doc_id: str, fmt: str) -> list[str]:
    sources = load_sources()
    if doc_id == "all":
        return [s.doc_id for s in sources.values() if s.format == fmt]
    if doc_id not in sources:
        raise typer.BadParameter(f"unknown doc_id {doc_id!r}; known: {', '.join(sources)}")
    if sources[doc_id].format != fmt:
        raise typer.BadParameter(f"{doc_id} is a {sources[doc_id].format} source, not {fmt}")
    return [doc_id]


@ingest.command("pages")
def ingest_pages(doc_id: str = typer.Argument(..., help="scan doc_id from data/sources.yaml, or 'all'")):
    """Extract page images of scanned sources into data/derived/<doc_id>/pages/."""
    from yhdp.ingest.scans import extract_pages

    for did in _doc_ids(doc_id, "scan"):
        out = settings.derived_dir / did / "pages"
        pages = extract_pages(load_sources()[did].resolve(), out)
        blanks = [p.index for p in pages if p.blank]
        typer.echo(f"{did}: {len(pages)} pages → {out} (blank: {blanks or 'none'})")


@ingest.command("parse")
def ingest_parse(doc_id: str = typer.Argument(..., help="doc_id from data/sources.yaml, or 'all'")):
    """Parse native .docx sources into data/derived/<doc_id>/parsed.json + outline.md."""
    from yhdp.ingest.parse_docx import outline, parse_docx

    for did in _doc_ids(doc_id, "docx"):
        source = load_sources()[did]
        out = settings.derived_dir / did
        doc = parse_docx(source.resolve(), source, out / "figures")
        doc.save(out / "parsed.json")
        (out / "outline.md").write_text(outline(doc), encoding="utf-8")
        typer.echo(f"{did}: {len(doc.blocks)} blocks → {out / 'parsed.json'}")
        typer.echo("  " + outline(doc).strip().splitlines()[-1])


@ingest.command("chunk")
def ingest_chunk(doc_id: str = typer.Argument(..., help="parsed doc_id, or 'all'")):
    """Chunk data/derived/<doc_id>/parsed.json into chunks.jsonl (scans: after OCR, P0 T10)."""
    from yhdp.ingest.chunk import chunk_doc, save_chunks, stats
    from yhdp.ingest.model import ParsedDoc

    for did in _doc_ids(doc_id, "docx"):
        out = settings.derived_dir / did
        chunks = chunk_doc(ParsedDoc.load(out / "parsed.json"), load_sources()[did])
        save_chunks(chunks, out / "chunks.jsonl")
        typer.echo(f"{did}: {stats(chunks)}")


@dictionary.command("check")
def dict_check() -> None:
    """Validate data/dictionary/terms.yaml (alias conflicts, duplicate canonicals)."""
    from yhdp.dictionary import load_dictionary

    dic = load_dictionary()
    typer.echo(f"terms.yaml OK: {len(dic.terms)} terms, {len(dic.by_key)} forms")


@dictionary.command("mine")
def dict_mine(llm_resolve: bool = typer.Option(True, "--llm/--no-llm",
                                               help="ask the LLM to expand unresolved (ABBR)")):
    """Mine suggestions from parsed docs into suggestions.jsonl and the review queue."""
    import json

    from yhdp.dictionary import load_dictionary
    from yhdp.ingest.mine_terms import (
        merge,
        mine_abbreviation_list,
        mine_paren_abbreviations,
        resolve_with_llm,
    )
    from yhdp.ingest.model import ParsedDoc
    from yhdp.llm import Ollama
    from yhdp.store.db import connect

    found, unresolved = [], []
    for did in _doc_ids("all", "docx"):
        doc = ParsedDoc.load(settings.derived_dir / did / "parsed.json")
        resolved, pending = mine_paren_abbreviations(doc)
        found += mine_abbreviation_list(doc) + resolved
        unresolved += pending
    if llm_resolve and unresolved:
        found += resolve_with_llm(unresolved, Ollama())
    suggestions = merge(found, load_dictionary())
    out = settings.data_dir / "dictionary" / "suggestions.jsonl"
    out.write_text("".join(s.model_dump_json() + "\n" for s in suggestions), encoding="utf-8")
    con = connect()
    with con:
        con.executemany(
            "INSERT INTO review_items (kind, ref, payload) VALUES ('dictionary', ?, ?) "
            "ON CONFLICT (kind, ref) DO UPDATE SET payload = excluded.payload",
            [(f"{s.alias}={s.canonical}", json.dumps(s.model_dump(), ensure_ascii=False))
             for s in suggestions])
    conflicts = sum(1 for s in suggestions if s.known_as)
    typer.echo(f"{len(suggestions)} suggestions → {out} ({conflicts} touch an existing term); "
               f"{len(unresolved)} unresolved (ABBR) mentions")


@tag.command("run")
def tag_run(pilot: bool = typer.Option(False, help="only the fixed 30-chunk pilot sample"),
            doc: str = typer.Option(None, help="only this doc_id"),
            limit: int = typer.Option(None, help="stop after N chunks"),
            force: bool = typer.Option(False, help="re-tag chunks that already have auto tags")):
    """Tag chunks with the LLM (2 runs each); disagreements go to the review queue."""
    import time

    from yhdp.ingest.tag import pending, pilot_ids, system_prompt, tag_chunk
    from yhdp.llm import LLMError, Ollama
    from yhdp.store.db import connect

    con, llm, system = connect(), Ollama(), system_prompt()
    todo = pending(con, pilot_ids(con) if pilot else None, force=force)
    if doc:
        todo = [c for c in todo if c["doc_id"] == doc]
    todo = todo[:limit] if limit else todo
    counts: dict[str, int] = {}
    t0 = time.monotonic()
    for i, chunk in enumerate(todo, start=1):
        try:
            status, reasons = tag_chunk(con, llm, chunk, load_sources()[chunk["doc_id"]], system)
        except LLMError as e:  # one bad chunk shouldn't stop an hour-long run; re-run retries it
            status, reasons = "error", [str(e).splitlines()[0]]
        counts[status] = counts.get(status, 0) + 1
        typer.echo(f"[{i}/{len(todo)}] {status:6} {chunk['chunk_id']}"
                   + (f"  ({', '.join(reasons)})" if reasons else ""))
    rate = counts.get("review", 0) / max(len(todo), 1)
    typer.echo(f"tagged {len(todo)} chunks in {time.monotonic() - t0:.0f}s: {counts}; "
               f"queue rate {rate:.0%}")


@tag.command("audit")
def tag_audit(n: int = typer.Option(30, help="how many unqueued auto-tagged chunks to sample")):
    """Queue a random sample of confident (unqueued) chunks for review, for an unbiased eval."""
    from yhdp.ingest.tag import queue_audit
    from yhdp.store.db import connect

    typer.echo(f"queued {queue_audit(connect(), n)} audit chunks")


@mcq.command("generate")
def mcq_generate(n: int = typer.Option(20, help="items to attempt (some are discarded)"),
                 van_de: int = typer.Option(None, help="only this vấn đề"),
                 seed: int = typer.Option(0)):
    """Generate and validate MCQs from MCQ-eligible chunks, spread by blueprint weights."""
    import time

    from yhdp.llm import Ollama
    from yhdp.mcq.generate import generate_item, plan_targets
    from yhdp.store.db import connect

    con, llm = connect(), Ollama()
    targets = plan_targets(con, n, van_de=van_de, seed=seed)
    counts: dict[str, int] = {}
    t0 = time.monotonic()
    for i, t in enumerate(targets, start=1):
        iid, status, problems = generate_item(con, llm, t, seed=seed)
        counts[status] = counts.get(status, 0) + 1
        typer.echo(f"[{i}/{len(targets)}] {status:9} #{iid} vấn đề {t.van_de} {t.chunk_id}"
                   + (f"  ({', '.join(problems)})" if problems else ""))
    typer.echo(f"done in {time.monotonic() - t0:.0f}s: {counts}")


@mcq.command("stats")
def mcq_stats():
    """Item bank counts by status and đề mục, and why items were discarded."""
    import json

    from yhdp.mcq.bank import stats
    from yhdp.store.db import connect

    typer.echo(json.dumps(stats(connect()), ensure_ascii=False, indent=1))


@report.command("coverage")
def report_coverage():
    """Vấn đề × document chunk counts → eval/reports/coverage.md."""
    from yhdp.reports import coverage
    from yhdp.store.db import connect

    text = coverage(connect())
    out = settings.root / "eval" / "reports" / "coverage.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    typer.echo("Gaps" + text.split("## Gaps")[1].splitlines()[0])
    typer.echo(f"→ {out}")


@report.command("tags")
def report_tags():
    """Model tags vs reviewer tags (T18) → eval/reports/p0-tagging.md."""
    from yhdp.reports import tag_eval
    from yhdp.store.db import connect

    text = tag_eval(connect())
    out = settings.root / "eval" / "reports" / "p0-tagging.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    typer.echo(text)
    typer.echo(f"→ {out}")


@tag.command("report")
def tag_report(pilot: bool = typer.Option(False, help="also write the pilot review sheet")):
    """Summarize auto tags: queue rate, reasons, Bloom and vấn đề distribution per doc."""
    import json
    from collections import Counter

    from yhdp.ingest.tag import pilot_ids
    from yhdp.store.db import connect

    con = connect()
    rows = con.execute(
        "SELECT c.doc_id, c.chunk_id, c.kind, c.text, t.tags FROM chunks c JOIN chunk_tags t "
        "ON t.chunk_id = c.chunk_id AND t.content_hash = c.content_hash AND t.source = 'auto'"
    ).fetchall()
    total = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
    recs = [json.loads(r["tags"]) for r in rows]
    typer.echo(f"tagged {len(recs)}/{total} chunks")
    for did in sorted({r["doc_id"] for r in rows}):
        mine = [rec for r, rec in zip(rows, recs, strict=True) if r["doc_id"] == did]
        queued = sum(rec["review_status"] == "review" for rec in mine)
        bloom = Counter(rec["bloom_ceiling"]["level"] for rec in mine)
        top = Counter(rec["blueprint"]["van_de"][0]["id"] for rec in mine).most_common(5)
        typer.echo(f"  {did}: {len(mine)} tagged, queue {queued / len(mine):.0%}; "
                   f"MCQ-eligible {sum(rec['mcq_eligible'] for rec in mine)}; "
                   f"Bloom {dict(bloom)}; top vấn đề {top}")
    reasons = Counter(x for (p,) in con.execute(
        "SELECT payload FROM review_items WHERE kind = 'tag' AND status = 'open'")
        for x in json.loads(p)["reasons"])
    typer.echo(f"  review reasons: {dict(reasons)}")
    if not pilot:
        return
    from yhdp.blueprint import load_blueprint

    bp = load_blueprint()
    by_id = {r["chunk_id"]: (r, rec) for r, rec in zip(rows, recs, strict=True)}
    lines = ["# Tagging pilot — review sheet", "",
             ("Each chunk: source location, text excerpt, the model's tags (run 1) and why it was "
             "queued. Mark anything wrong."), ""]
    for n, cid in enumerate(pilot_ids(con), start=1):
        if cid not in by_id:
            continue
        r, rec = by_id[cid]
        item = con.execute("SELECT payload FROM review_items WHERE kind = 'tag' AND ref = ?",
                           (cid,)).fetchone()
        runs = json.loads(item["payload"])["runs"] if item else None
        vd = "; ".join(f"{'**' if v['primary'] else ''}{v['id']}. {bp.van_de_by_id(v['id']).name}"
                       f"{'**' if v['primary'] else ''} ({v['conf']:.2f})"
                       for v in rec["blueprint"]["van_de"])
        mien = "; ".join(f"{m['id']} {m['label']} ({m['conf']:.2f})" for m in rec["blueprint"]["mien"])
        excerpt = r["text"][:700].replace("\n", "\n> ")
        lines += [f"## {n}. `{cid}` ({r['kind']})", "",
                  f"**Vị trí:** {' › '.join(rec['source']['section_path'])}", "",
                  f"> {excerpt}{'…' if len(r['text']) > 700 else ''}", "",
                  f"- **Vấn đề:** {vd}", f"- **Miền:** {mien}",
                  (f"- **Bloom trần:** {rec['bloom_ceiling']['level']} "
                  f"({rec['bloom_ceiling']['conf']:.2f}) · **Loại:** {rec['content_type']} · "
                  f"**Đối tượng:** {', '.join(rec['population']) or '—'}"),
                  f"- **Lý do (model):** {rec['ly_do']}",
                  f"- **Trạng thái:** {rec['review_status']}"
                  + (f" — {', '.join(json.loads(item['payload'])['reasons'])}" if item else "")]
        if runs:
            r2 = runs[1]
            p2 = next(v["id"] for v in r2["van_de"] if v["primary"])
            lines.append(f"- **Run 2:** vấn đề {p2}, miền "
                         f"{max(r2['mien'], key=lambda m: m['conf'])['id']}, "
                         f"Bloom {r2['bloom_ceiling']['level']}")
        lines.append("")
    out = settings.derived_dir / "tag_pilot.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    typer.echo(f"pilot review sheet → {out}")


@user.command("add")
def user_add(username: str, role: str = typer.Option("reviewer", help="reviewer | learner"),
             password: str = typer.Option(None, help="omit to generate a random one")):
    """Create or reset a web app account; prints a generated password if none is given."""
    import secrets

    from yhdp.api.auth import add_user
    from yhdp.store.db import connect

    if role not in ("reviewer", "learner"):
        raise typer.BadParameter("role must be reviewer or learner")
    generated = password is None
    password = password or secrets.token_urlsafe(12)
    add_user(connect(), username, password, role)
    typer.echo(f"{role} {username!r} saved" + (f"; password: {password}" if generated else ""))


@app.command()
def serve(host: str = typer.Option("127.0.0.1", help="0.0.0.0 to listen on the LAN"),
          port: int = typer.Option(8000)):
    """Run the API, optionally serving local built React assets."""
    import uvicorn

    from yhdp.api.app import create_app

    uvicorn.run(create_app(), host=host, port=port, proxy_headers=True,
                forwarded_allow_ips="127.0.0.1")


@app.command()
def index() -> None:
    """Load every chunks.jsonl into SQLite and embed new or changed chunks."""
    from yhdp.ingest.chunk import load_chunks
    from yhdp.ingest.load_db import embed_missing, load_doc
    from yhdp.llm import Ollama
    from yhdp.store.db import connect

    con = connect()
    for did, source in load_sources().items():
        path = settings.derived_dir / did / "chunks.jsonl"
        if not path.exists():
            typer.echo(f"{did}: no chunks yet, skipped")
            continue
        typer.echo(f"{did}: {load_doc(con, source, load_chunks(path))}")
    typer.echo(f"embedded {embed_missing(con, Ollama())} chunks with {settings.embed_model}")


@app.command()
def ask(question: str = typer.Argument(None, help="omit for an interactive session"),
        k: int = typer.Option(6, help="number of source chunks given to the model"),
        think: bool = typer.Option(False, help="let the model reason first (slower)"),
        debug: bool = typer.Option(False, help="show retrieval ranks")):
    """Ask a cited question about the indexed documents (terminal preview of the chatbot)."""
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown

    from yhdp.answer import citation, cited, stream_answer
    from yhdp.dictionary import load_dictionary
    from yhdp.llm import Ollama
    from yhdp.retrieve import Retriever
    from yhdp.store.db import connect

    console, con, llm = Console(), connect(), Ollama()
    retriever = Retriever(con, llm, dictionary=load_dictionary())
    history: list[dict] = []
    while True:
        q = question or console.input("[bold cyan]Hỏi>[/] ").strip()
        if not q or q in {"q", "quit", "exit"}:
            return
        hits = retriever.search(q, k=k)
        text = ""
        with Live(Markdown(""), console=console, refresh_per_second=8) as live:
            for piece in stream_answer(llm, con, q, hits, think=think, history=history[-4:]):
                text += piece
                live.update(Markdown(text))
        used, bad = cited(text, len(hits))
        console.print("\n[bold]Nguồn[/]")
        for i, h in enumerate(hits, start=1):
            mark = "[green]●[/]" if i in used else "[dim]○[/]"
            fig = f"  [dim]{h.extra['figure_path']}[/]" if h.extra.get("figure_path") else ""
            ranks = f"  [dim]{h.ranks}[/]" if debug else ""
            console.print(f" {mark} [S{i}] {citation(con, h)}{fig}{ranks}", highlight=False)
        if not used:
            console.print("[yellow]⚠ Câu trả lời không trích dẫn nguồn nào.[/]")
        if bad:
            console.print(f"[red]⚠ Trích dẫn không tồn tại: {bad}[/]")
        if question:
            return
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": text}]
        console.print()


@app.command()
def sources() -> None:
    """List registered source documents and the files they resolve to."""
    for s in load_sources().values():
        try:
            target = s.resolve().name
        except LookupError as e:
            target = f"ERROR: {e}"
        typer.echo(f"{s.doc_id:8} {s.format:5} {s.kind:9} {target}")


@app.command()
def blueprint() -> None:
    """Summarize the QĐ 51 blueprint and how many vấn đề descriptions are approved."""
    bp = load_blueprint()
    for d in bp.de_muc:
        vds = [v for v in bp.van_de if v.de_muc == d.id]
        ok = sum(v.approved for v in vds)
        typer.echo(f"Đề mục {d.id} ({d.weight[0]}–{d.weight[1]}%): {len(vds)} vấn đề, "
                   f"{ok} approved — {d.name}")
    typer.echo(f"Miền sub-contents: {len(bp.mien_subs())}")


if __name__ == "__main__":
    app()
