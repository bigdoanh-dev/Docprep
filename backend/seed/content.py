"""Load the content files, check them against the blueprint, and write them.

Demo fixture: the seed approves questions and content items by writing two review decisions from the
demo reviewers, so the history says truthfully how each item was approved. Dev and test only.
"""
from pathlib import Path

import yaml
from psycopg.types.json import Jsonb

from app.config import settings
from app.engine.blueprint import FOUNDATION_CODE, Competency, FormItem, check_form, issue_code
from app.text import unaccent  # noqa: F401  (re-exported: the loader's callers import it from here)
from seed.blueprint import component_ids, groups_of, module_id

CONTENT_DIR = Path(__file__).with_name("content")
FILES = ("documents", "glossary", "modules", "questions", "exam_forms")
FORM_KINDS = ("diagnostic", "mock", "demo_short", "assembled")
DEMO_COMMENT = "Dữ liệu demo – chưa thẩm định"
APPROVED = "approved"


def load_content(content_dir: Path = CONTENT_DIR) -> dict:
    out = {}
    for name in FILES:
        with open(Path(content_dir) / f"{name}.yaml", encoding="utf-8") as f:
            out[name] = yaml.safe_load(f) or []
    return out


def core_issue_of(competency_code: str) -> int | None:
    """The core issue of a topic code: CI-04 → 4; the foundation topic has none."""
    return int(competency_code[3:]) if competency_code.startswith("CI-") else None


def _dupes(ids: list[str], kind: str) -> list[str]:
    seen, errors = set(), []
    for i in ids:
        if i in seen:
            errors.append(f"duplicate {kind} id {i}")
        seen.add(i)
    return errors


def _competencies(blueprint: dict) -> list[Competency]:
    ids = component_ids(blueprint)
    return [Competency(c["id"], c["name"], c["weight_min"], c["weight_max"], ids[c["id"]])
            for c in blueprint["competencies"]]


def validate_content(content: dict, blueprint: dict) -> list[str]:
    errors: list[str] = []
    labels = settings()["elo"]["initial_b"]
    groups = groups_of(blueprint)
    codes = {issue_code(i) for g in groups for i in g.issue_ids} | {FOUNDATION_CODE}
    components = {c for ids in component_ids(blueprint).values() for c in ids}
    module_ids = {module_id(g.id) for g in groups}
    passages = [p for d in content["documents"] for p in d.get("passages", [])]
    passage_ids = {p["id"] for p in passages}
    questions = {q["id"]: q for q in content["questions"]}

    errors += _dupes([d["id"] for d in content["documents"]], "document")
    errors += _dupes([p["id"] for p in passages], "passage")
    errors += _dupes([q["id"] for q in content["questions"]], "question")

    for d in content["documents"]:
        if not d.get("demo_label"):
            errors.append(f"document {d['id']}: missing demo_label")
    for p in passages:
        if not p.get("page") and not p.get("article"):
            errors.append(f"passage {p['id']}: needs page or article")
        if p.get("competency_code") not in codes:
            errors.append(f"passage {p['id']}: unknown competency {p.get('competency_code')}")

    for q in content["questions"]:
        where = f"question {q['id']}"
        opts = q.get("options", [])
        if len(opts) < 2:
            errors.append(f"{where}: needs at least 2 options")
        if sum(1 for o in opts if o.get("correct")) != 1:
            errors.append(f"{where}: needs exactly one correct option")
        if any(not o.get("rationale") for o in opts):
            errors.append(f"{where}: every option needs a rationale")
        if not q.get("explanation"):
            errors.append(f"{where}: missing explanation")
        for s in q.get("sources", []):
            if s not in passage_ids:
                errors.append(f"{where}: unknown passage {s}")
        if not q.get("sources"):
            errors.append(f"{where}: needs at least one source")
        if q.get("competency_code") not in codes:
            errors.append(f"{where}: unknown competency {q.get('competency_code')}")
        if q.get("exam_competency_component") not in components:
            errors.append(f"{where}: unknown component {q.get('exam_competency_component')}")
        if q.get("bloom_level") not in (1, 2, 3):
            errors.append(f"{where}: bloom_level must be 1, 2 or 3")
        if q.get("difficulty") not in labels:
            errors.append(f"{where}: unknown difficulty {q.get('difficulty')}")

    for m in content["modules"]:
        if m.get("module") not in module_ids:
            errors.append(f"modules: unknown module {m.get('module')}")
        for c in m.get("extra_competency_codes", []):
            if c not in codes:
                errors.append(f"module {m.get('module')}: unknown competency {c}")
        for u in m.get("units", []):
            if u.get("competency_code") not in codes:
                errors.append(f"unit {u['id']}: unknown competency {u.get('competency_code')}")
            quiz_ids = {i["id"] for i in u["items"] if i["kind"] == "quiz"}
            for i in u["items"]:
                where = f"unit item {i['id']}"
                if i["kind"] == "quiz" and i.get("question") not in questions:
                    errors.append(f"{where}: unknown question {i.get('question')}")
                if i["kind"] in ("content", "remediation"):
                    for s in i["content"].get("sources", []):
                        if s not in passage_ids:
                            errors.append(f"{where}: unknown passage {s}")
                if i["kind"] == "remediation" and i.get("after") not in quiz_ids:
                    errors.append(f"{where}: remediation must follow a quiz item in the same unit")

    competencies = _competencies(blueprint)
    for f in content["exam_forms"]:
        where = f"exam form {f['id']}"
        unknown = [qid for qid in f["questions"] if qid not in questions]
        errors += [f"{where}: unknown question {qid}" for qid in unknown]
        if f.get("kind") not in FORM_KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(FORM_KINDS)}")
        if f.get("kind") == "assembled":
            size = f.get("n_questions")
            if not isinstance(size, int) or not 0 < size <= len(questions):
                errors.append(f"{where}: n_questions must be between 1 and the size of the question bank")
        if f.get("kind") == "mock" and not unknown:
            # A mock must follow the blueprint: group and competency shares within range, no recall items.
            items = [FormItem(qid, core_issue_of(questions[qid].get("competency_code") or ""),
                              questions[qid].get("exam_competency_component"), questions[qid].get("bloom_level") or 0)
                     for qid in f["questions"]]
            errors += [f"{where}: {problem}" for problem in check_form(items, groups, competencies).problems]
    return errors


TABLES = {"question": "question", "content": "content_item"}


def _approve(conn, target_type: str, item_id: str, reviewers: list[dict]) -> None:
    """Take a draft through every status with the two demo reviewers, leaving the decisions and the
    history. The database accepts `approved` only from the second review round, on two passes."""
    table = TABLES[target_type]
    first, second = reviewers
    # (from, to, reviewer deciding this step or None, label of who moved it)
    steps = [
        (None, "draft", None, "Nạp dữ liệu"),
        ("draft", "prescreen", None, "Hệ thống"),
        ("prescreen", "in_review_r1", None, "Hệ thống"),
        ("in_review_r1", "in_review_r2", (1, first), first["display_name"]),
        ("in_review_r2", APPROVED, (2, second), second["display_name"]),
    ]
    for from_status, to_status, decision, actor_label in steps:
        if decision:
            round_, reviewer = decision
            conn.execute(
                """insert into review_decision(target_type, target_id, version, round, reviewer_id, decision, comment)
                   values (%s, %s, 1, %s, %s, 'pass', %s)""",
                (target_type, item_id, round_, reviewer["id"], DEMO_COMMENT))
        if from_status is not None:
            conn.execute(f"update {table} set status = %s where id = %s and version = 1", (to_status, item_id))
        conn.execute(
            """insert into status_transition(target_type, target_id, version, from_status, to_status, actor_id,
               actor_label, reason) values (%s, %s, 1, %s, %s, %s, %s, %s)""",
            (target_type, item_id, from_status, to_status, decision[1]["id"] if decision else None, actor_label,
             DEMO_COMMENT if decision else None))


def _stored(conn, target_type: str, item_id: str, columns: tuple[str, ...]) -> dict | None:
    return conn.execute(
        f"select {', '.join(columns)} from {TABLES[target_type]} where id = %s and version = 1", (item_id,)).fetchone()


def _unchanged_or_refuse(kind: str, item_id: str, stored: dict, wanted: dict) -> None:
    """An item already in the database is approved and frozen: the file must still say the same."""
    changed = sorted(k for k, v in wanted.items() if stored[k] != v)
    if changed:
        raise ValueError(
            f"{kind} {item_id} is already approved and the file now differs in {', '.join(changed)}. "
            "An approved item is never edited: run `python -m app.cli reset-dev`, or author it as a new version.")


def write_content(conn, content: dict, blueprint: dict, reviewers: tuple[int, int]) -> None:
    """Upsert the content. New questions and content items are approved through recorded demo decisions."""
    errors = validate_content(content, blueprint)
    if errors:
        raise ValueError("invalid seed content:\n" + "\n".join(errors))

    cfg = settings()
    corpus, initial_b = cfg["corpus_version"], cfg["elo"]["initial_b"]
    reviewer_rows = [conn.execute("select id, display_name from staff_user where id = %s", (r,)).fetchone()
                     for r in reviewers]

    for d in content["documents"]:
        note = " ".join(d["validity_note"].split()) if d.get("validity_note") else None
        conn.execute(
            """insert into document(id, title, edition, excerpt_limit, demo_label, validity_status, validity_note)
               values (%s, %s, %s, %s, %s, %s, %s)
               on conflict (id) do update set title = excluded.title, edition = excluded.edition,
                 excerpt_limit = excluded.excerpt_limit, demo_label = excluded.demo_label,
                 validity_status = excluded.validity_status, validity_note = excluded.validity_note""",
            (d["id"], d["title"], d.get("edition"), d.get("excerpt_limit"), d["demo_label"],
             "superseded" if note else "valid", note))
        for p in d["passages"]:
            context = " ".join(x for x in (d["title"], p.get("chapter"), p.get("section")) if x)
            text = p["text"].strip()
            conn.execute(
                """insert into passage(id, document_id, chapter, section, page_start, page_end, article,
                   competency_code, text, text_unaccented, corpus_version, context, context_unaccented)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   on conflict (id) do update set document_id = excluded.document_id, chapter = excluded.chapter,
                     section = excluded.section, page_start = excluded.page_start, page_end = excluded.page_end,
                     article = excluded.article, competency_code = excluded.competency_code, text = excluded.text,
                     text_unaccented = excluded.text_unaccented, corpus_version = excluded.corpus_version,
                     context = excluded.context, context_unaccented = excluded.context_unaccented""",
                (p["id"], d["id"], p.get("chapter"), p.get("section"), p.get("page"), p.get("page_end", p.get("page")),
                 p.get("article"), p["competency_code"], text, unaccent(text), corpus, context, unaccent(context)))

    for g in content["glossary"]:
        conn.execute(
            """insert into glossary_term(term, synonyms) select %s, %s
               where not exists (select 1 from glossary_term where term = %s)""",
            (g["term"], g.get("synonyms", []), g["term"]))
        conn.execute("update glossary_term set ambiguous = %s, sense_group = %s where term = %s",
                     (bool(g.get("ambiguous", False)), g.get("sense_group"), g["term"]))

    for q in content["questions"]:
        options = [{"key": o["key"], "text": str(o["text"]), "is_correct": bool(o.get("correct")),
                    "rationale": o["rationale"]} for o in q["options"]]
        wanted = {
            "stem": q["stem"].strip(), "options": options, "explanation": q["explanation"].strip(),
            "competency_code": q["competency_code"], "core_issue_id": core_issue_of(q["competency_code"]),
            "exam_competency_component_id": q["exam_competency_component"], "bloom_level": q["bloom_level"],
            "difficulty_label": q["difficulty"], "source_passage_ids": q["sources"],
        }
        stored = _stored(conn, "question", q["id"], tuple(wanted))
        if stored is not None:
            _unchanged_or_refuse("question", q["id"], stored, wanted)
            continue
        conn.execute(
            """insert into question(stem, options, explanation, competency_code, core_issue_id,
               exam_competency_component_id, bloom_level, difficulty_label, source_passage_ids, id, difficulty_b, status)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')""",
            (wanted["stem"], Jsonb(options), *list(wanted.values())[2:], q["id"], initial_b[q["difficulty"]]))
        _approve(conn, "question", q["id"], reviewer_rows)

    # The học phần rows come from the blueprint loader; here they get their extra topics and "Sắp có" flag.
    units_by_module = {m["module"]: m for m in content["modules"]}
    for g in blueprint["groups"]:
        mid = module_id(g["id"])
        entry = units_by_module.get(mid, {})
        codes = [issue_code(i["id"]) for i in g["issues"]] + list(entry.get("extra_competency_codes", []))
        conn.execute("update module set competency_codes = %s, coming_soon = %s where id = %s",
                     (codes, not entry.get("units"), mid))
        for u_ord, u in enumerate(entry.get("units", [])):
            conn.execute(
                """insert into unit(id, module_id, ord, topic, competency_code) values (%s, %s, %s, %s, %s)
                   on conflict (id) do update set module_id = excluded.module_id, ord = excluded.ord,
                     topic = excluded.topic, competency_code = excluded.competency_code""",
                (u["id"], mid, u_ord, u["topic"], u["competency_code"]))
            for i_ord, i in enumerate(u["items"]):
                content_id = None
                if i["kind"] in ("content", "remediation"):
                    c = i["content"]
                    content_id = c["id"]
                    wanted = {"title": c.get("title"), "body": c["body"].strip(),
                              "source_passage_ids": c.get("sources", []), "competency_code": u["competency_code"]}
                    stored = _stored(conn, "content", c["id"], tuple(wanted))
                    if stored is not None:
                        _unchanged_or_refuse("content item", c["id"], stored, wanted)
                    else:
                        conn.execute(
                            """insert into content_item(title, body, source_passage_ids, competency_code, id, status)
                               values (%s, %s, %s, %s, %s, 'draft')""", (*wanted.values(), c["id"]))
                        _approve(conn, "content", c["id"], reviewer_rows)
                conn.execute(
                    """insert into unit_item(id, unit_id, ord, kind, content_id, question_id, after_item_id, note)
                       values (%s, %s, %s, %s, %s, %s, %s, %s)
                       on conflict (id) do update set unit_id = excluded.unit_id, ord = excluded.ord,
                         kind = excluded.kind, content_id = excluded.content_id, question_id = excluded.question_id,
                         after_item_id = excluded.after_item_id, note = excluded.note""",
                    (i["id"], u["id"], i_ord, i["kind"], content_id, i.get("question"), i.get("after"), i.get("note")))

    for f in content["exam_forms"]:
        conn.execute(
            """insert into exam_form(id, title, kind, question_ids, n_questions, seconds_per_question, max_attempts, status)
               values (%s, %s, %s, %s, %s, %s, %s, %s)
               on conflict (id) do update set title = excluded.title, kind = excluded.kind,
                 question_ids = excluded.question_ids, n_questions = excluded.n_questions,
                 seconds_per_question = excluded.seconds_per_question, max_attempts = excluded.max_attempts""",
            (f["id"], f["title"], f["kind"], f["questions"], f.get("n_questions"), f["seconds_per_question"],
             f.get("max_attempts"), APPROVED))
