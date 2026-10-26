"""Keyword retrieval over the seeded corpus (demo: no dense vectors, no reranker).

PostgreSQL full-text search finds candidates and gives the tie-break rank. The score that
orders results and gates "enough evidence?" is IDF-weighted coverage: how much of the
question's content (its loose tokens and glossary concepts) the passage actually contains.
A raw ts_rank_cd value cannot do that job: it is not comparable between a short and a long
question, so no threshold separates an out-of-corpus question from a short in-corpus one.
"""
import math
import re
from dataclasses import dataclass

from app.chat.normalise import Normalised, fold_dashes, tokens
from app.config import settings

_COLUMNS = """p.id, p.document_id, d.title as document_title, p.chapter, p.section, p.page_start, p.article,
              p.text, p.text_unaccented, p.context, p.context_unaccented, p.competency_code"""


@dataclass(frozen=True)
class Passage:
    id: str
    document_id: str
    document_title: str
    chapter: str | None
    section: str | None
    page_start: int | None
    article: str | None
    text: str
    score: float
    competency_code: str | None = None


@dataclass(frozen=True)
class Found:
    """What retrieval found: the passages that count as evidence, best first, and, when there is none,
    the candidate that came nearest to the threshold (None when nothing shared a word with the question)."""
    passages: list[Passage]
    nearest: Passage | None = None


def _passage(row: dict, score: float) -> Passage:
    return Passage(id=row["id"], document_id=row["document_id"], document_title=row["document_title"],
                   chapter=row["chapter"], section=row["section"], page_start=row["page_start"],
                   article=row["article"], text=row["text"], score=score, competency_code=row["competency_code"])


_REAL = "not exists (select 1 from document d where d.id = p.document_id and d.is_synthetic)"


def _idf(conn, terms: list[str]) -> dict[str, float]:
    # The sample bank's placeholder passages are not part of the corpus: they are neither counted nor found.
    total = conn.execute(f"select count(*) c from passage p where {_REAL}").fetchone()["c"]
    rows = conn.execute(
        f"""select t, (select count(*) from passage p where p.tsv @@ to_tsquery('simple', t) and {_REAL}) as df
           from unnest(%s::text[]) as t""", (terms,)).fetchall()
    return {r["t"]: math.log(1 + (total - r["df"] + 0.5) / (r["df"] + 0.5)) for r in rows}


def _has_phrase(haystack: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", haystack) is not None


def _coverage(n: Normalised, haystack: str, idf: dict[str, float]) -> float:
    present = set(tokens(haystack))
    covered = total = 0.0
    for tok in n.loose:
        total += idf[tok]
        if tok in present:
            covered += idf[tok]
    for forms in n.concepts:
        # A glossary concept counts as a whole: it is covered only when one of its forms
        # appears as a phrase, and it weighs as much as all the words of its canonical term.
        weight = sum(idf[t] for t in tokens(forms[0]))
        total += weight
        if any(_has_phrase(haystack, f) for f in forms):
            covered += weight
    return covered / total if total else 0.0


def search(conn, n: Normalised, top_k: int, min_score: float, module_id: str | None = None) -> list[Passage]:
    return find(conn, n, top_k, min_score, module_id).passages


def find(conn, n: Normalised, top_k: int, min_score: float, module_id: str | None = None) -> Found:
    if not n.terms:
        return Found([])
    tsquery = " | ".join(n.terms)  # terms are \w+ tokens, so no escaping is needed
    params: list = [tsquery, tsquery]
    module_filter = ""
    if module_id:
        module_filter = "and p.competency_code = any(select unnest(competency_codes) from module where id = %s)"
        params.append(module_id)
    rows = conn.execute(
        f"""select {_COLUMNS}, ts_rank_cd(p.tsv, to_tsquery('simple', %s), 1) as rank
            from passage p join document d on d.id = p.document_id
            where p.tsv @@ to_tsquery('simple', %s) and not d.is_synthetic {module_filter}""", params).fetchall()
    if not rows:
        return Found([])

    scoring_terms = list(dict.fromkeys(n.loose + [t for forms in n.concepts for f in forms for t in tokens(f)]))
    idf = _idf(conn, scoring_terms)
    # The evidence gate uses coverage alone. For ordering, a passage whose heading (document,
    # chapter, section) names what was asked gets a bonus: it is the passage *about* the topic,
    # not one that merely mentions it, and must not lose its place in the top k to a tie.
    heading_boost = settings()["retrieval"]["heading_boost"]
    scored, missed = [], []
    for row in rows:
        context = fold_dashes((row["context_unaccented"] if n.plain else row["context"]).lower())
        text = fold_dashes((row["text_unaccented"] if n.plain else row["text"]).lower())
        coverage = _coverage(n, f"{context} {text}", idf)
        if coverage >= min_score:
            scored.append((coverage + heading_boost * _coverage(n, context, idf), row["rank"], row))
        elif coverage > 0:
            missed.append((coverage, row["rank"], row))
    scored.sort(key=lambda s: (-s[0], -s[1], s[2]["id"]))
    if scored:
        return Found([_passage(row, score) for score, _rank, row in scored[:top_k]])
    missed.sort(key=lambda s: (-s[0], -s[1], s[2]["id"]))
    return Found([], _passage(missed[0][2], missed[0][0]) if missed else None)


def get_passages(conn, ids: list[str]) -> dict[str, Passage]:
    rows = conn.execute(
        f"select {_COLUMNS} from passage p join document d on d.id = p.document_id where p.id = any(%s)",
        (ids,)).fetchall()
    return {r["id"]: _passage(r, 0.0) for r in rows}
