"""The sample question bank: placeholder questions for every core issue, their review history, and
one mock form that follows the blueprint.

A sample question holds no medical text. A revision card needs a source, so each one cites the
placeholder passage of its core issue, in a document flagged `is_synthetic` that search and the
source sheet skip. The question itself is flagged too and served to synthetic learners only. It becomes approved
the way any question does: two passes, from two reviewers, checked by the database.
"""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from psycopg.types.json import Jsonb

from app.config import settings
from app.engine.blueprint import Competency, FormItem, check_form, issue_code
from app.text import unaccent
from seed.blueprint import component_ids, groups_of
from seed.cohort import params as P

SYSTEM, LOADER = "Hệ thống", "Nạp dữ liệu mẫu"
# Where a decision other than a pass sends the item.
SENT_TO = {"revise": "needs_revision", "reject": "rejected"}


@dataclass(frozen=True)
class AnswerKey:
    """What the simulation knows about a question and a learner does not."""
    correct: str
    wrong: tuple[str, ...]
    label_b: float      # the difficulty its label starts from


@dataclass(frozen=True)
class _Spec:
    id: str
    issue: int
    group: int
    component: int
    bloom: int


def _question_id(issue: int, n: int) -> str:
    return f"{P.SAMPLE_PREFIX}{issue:02d}-{n:03d}"


def _passage_id(issue: int) -> str:
    return f"{P.SAMPLE_PREFIX}P-{issue:02d}"


def _write_sources(conn, issues: list[int]) -> None:
    """The sample document and one placeholder passage per core issue, on the page of its number."""
    conn.execute(
        "insert into document(id, title, demo_label, is_synthetic) values (%s, %s, %s, true)",
        (P.SAMPLE_DOCUMENT_ID, P.SAMPLE_DOCUMENT_TITLE, P.SAMPLE_COMMENT))
    context = P.SAMPLE_DOCUMENT_TITLE
    for issue in issues:
        text = f"Đoạn mẫu {issue:02d}."
        conn.execute(
            """insert into passage(id, document_id, page_start, page_end, competency_code, text, text_unaccented,
                 corpus_version, context, context_unaccented) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (_passage_id(issue), P.SAMPLE_DOCUMENT_ID, issue, issue, issue_code(issue), text, unaccent(text),
             settings()["corpus_version"], context, unaccent(context)))


def _days(rng: random.Random, low: float, high: float) -> timedelta:
    return timedelta(days=rng.uniform(low, high))


def _insert(conn, spec: _Spec, rng: random.Random) -> None:
    """One placeholder question, as a draft."""
    correct = rng.choice("ABCD")
    options = [{"key": key, "text": f"Phương án {key}", "is_correct": key == correct, "rationale": "Giải thích mẫu"}
               for key in "ABCD"]
    label = rng.choices(list(P.DIFFICULTY_WEIGHTS), weights=list(P.DIFFICULTY_WEIGHTS.values()))[0]
    conn.execute(
        """insert into question(id, stem, options, explanation, competency_code, core_issue_id,
             exam_competency_component_id, bloom_level, difficulty_label, difficulty_b, source_passage_ids,
             status, is_synthetic)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', true)""",
        (spec.id, f"Câu mẫu {spec.id[len(P.SAMPLE_PREFIX):]} · nhóm {spec.group}", Jsonb(options),
         "Giải thích mẫu – không phải nội dung chuyên môn.", issue_code(spec.issue), spec.issue, spec.component,
         spec.bloom, label, settings()["elo"]["initial_b"][label], [_passage_id(spec.issue)]))


def _walk(conn, question_id: str, steps: list[tuple]) -> None:
    """Write a question's history. A step is (at, to_status, decision); a decision is None for a
    step the system took, else (round, reviewer row, 'pass' | 'revise' | 'reject'). The decision is
    recorded before the status moves: the database reads it to allow `approved`."""
    current = None
    for at, to_status, decision in steps:
        if decision:
            round_, reviewer, verdict = decision
            conn.execute(
                """insert into review_decision(target_type, target_id, version, round, reviewer_id, decision,
                     comment, created_at) values ('question', %s, 1, %s, %s, %s, %s, %s)""",
                (question_id, round_, reviewer["id"], verdict, P.SAMPLE_COMMENT, at))
        if current is not None:
            conn.execute("update question set status = %s where id = %s and version = 1", (to_status, question_id))
        conn.execute(
            """insert into status_transition(target_type, target_id, version, from_status, to_status, actor_id,
                 actor_label, at, reason) values ('question', %s, 1, %s, %s, %s, %s, %s, %s)""",
            (question_id, current, to_status, decision[1]["id"] if decision else None,
             decision[1]["display_name"] if decision else (LOADER if current is None else SYSTEM), at,
             P.SAMPLE_COMMENT if decision else None))
        current = to_status


def _steps(reviewers: list[dict], drafted: datetime, r1_in: datetime | None = None,
           r1: tuple[datetime, str] | None = None, r2: tuple[datetime, str] | None = None) -> list[tuple]:
    """The history of one question, as far as it got. `r1` and `r2` are (when, decision); an item
    enters round 2 at the moment round 1 passes it."""
    first, second = reviewers
    steps = [(drafted, "draft", None)]
    if r1_in is None:
        return steps
    steps += [(drafted, "prescreen", None), (r1_in, "in_review_r1", None)]
    if r1:
        at, verdict = r1
        steps.append((at, SENT_TO.get(verdict, "in_review_r2"), (1, first, verdict)))
    if r2:
        at, verdict = r2
        steps.append((at, SENT_TO.get(verdict, "approved"), (2, second, verdict)))
    return steps


def _reviewer_rows(conn, reviewers: tuple[int, int]) -> list[dict]:
    return [conn.execute("select id, display_name from staff_user where id = %s", (r,)).fetchone() for r in reviewers]


def _competencies(blueprint: dict) -> list[Competency]:
    ids = component_ids(blueprint)
    return [Competency(c["id"], c["name"], c["weight_min"], c["weight_max"], ids[c["id"]])
            for c in blueprint["competencies"]]


def _core_specs(blueprint: dict, rng: random.Random) -> tuple[list[_Spec], list[_Spec]]:
    """Every approved question of the core bank, and the forty among them that make the mock form.

    The form's places are handed out first: for each group, `FORM_SPLIT` says how many questions of
    each exam competency it holds, and they go round the group's issues in turn."""
    components = component_ids(blueprint)
    every_component = [c for ids in components.values() for c in ids]
    specs, in_form = [], []
    for group in groups_of(blueprint):
        places: dict[int, list[int]] = {}      # issue → the competencies of its questions on the form
        wanted = [competency for competency, count in enumerate(P.FORM_SPLIT[group.id], start=1) for _ in range(count)]
        for i, competency in enumerate(wanted):
            places.setdefault(group.issue_ids[i % len(group.issue_ids)], []).append(competency)
        for issue in group.issue_ids:
            count = P.APPROVED_THIN if issue in P.THIN_ISSUES else P.APPROVED_PER_ISSUE
            on_form = places.get(issue, [])
            for n in range(1, count + 1):
                component = components[on_form[n - 1]][0] if n <= len(on_form) else rng.choice(every_component)
                spec = _Spec(_question_id(issue, n), issue, group.id, component, rng.choice((2, 3)))
                specs.append(spec)
                if n <= len(on_form):
                    in_form.append(spec)
    return specs, in_form


def write_core(conn, blueprint: dict, reviewers: tuple[int, int], approved_by: datetime, rng: random.Random) -> None:
    """The approved sample questions, each with a review history that ends before `approved_by`, and
    the sample mock form. The form is checked against the blueprint before anything is written."""
    specs, in_form = _core_specs(blueprint, rng)
    report = check_form([FormItem(s.id, s.issue, s.component, s.bloom) for s in in_form],
                        groups_of(blueprint), _competencies(blueprint))
    if report.problems:
        raise ValueError("the sample mock form does not follow the blueprint:\n" + "\n".join(report.problems))

    rows = _reviewer_rows(conn, reviewers)
    _write_sources(conn, sorted({spec.issue for spec in specs}))
    for spec in specs:
        _insert(conn, spec, rng)
        approved_at = approved_by - _days(rng, 0, 30)
        r1_at = approved_at - _days(rng, *P.R2_DAYS)
        r1_in = r1_at - _days(rng, *P.R1_DAYS)
        _walk(conn, spec.id, _steps(rows, r1_in - _days(rng, 0, 3), r1_in, (r1_at, "pass"), (approved_at, "pass")))

    conn.execute(
        """insert into exam_form(id, title, kind, question_ids, seconds_per_question, status, is_synthetic)
           values (%s, %s, 'mock', %s, %s, 'approved', true)""",
        (P.SAMPLE_FORM_ID, P.SAMPLE_FORM_TITLE, [s.id for s in in_form], P.SECONDS_PER_QUESTION))


def write_pipeline(conn, blueprint: dict, reviewers: tuple[int, int], start: datetime, end: datetime,
                   rng: random.Random) -> None:
    """The rest of the bank's life, dated inside the cohort's weeks: late approvals, items waiting in
    each round, items sent back or rejected, and drafts. Written after the learners' histories, so no
    learner was served an item before its approval."""
    rows = _reviewer_rows(conn, reviewers)
    groups = groups_of(blueprint)
    group_of = {issue: g.id for g in groups for issue in g.issue_ids}
    every_component = [c for ids in component_ids(blueprint).values() for c in ids]
    issues = sorted(group_of)
    next_n = {issue: conn.execute("select count(*) n from question where id like %s",
                                  (f"{P.SAMPLE_PREFIX}{issue:02d}-%",)).fetchone()["n"] + 1 for issue in issues}

    def moment() -> datetime:
        return start + (end - start) * rng.random()

    def back(at: datetime, low: float, high: float) -> datetime:
        return max(start, at - _days(rng, low, high))

    for outcome, count in P.PIPELINE.items():
        for _ in range(count):
            # A late approval never lifts a thin issue over the line: those stay under 10 approved.
            issue = rng.choice([i for i in issues if i not in P.THIN_ISSUES] if outcome == "approved" else issues)
            spec = _Spec(_question_id(issue, next_n[issue]), issue, group_of[issue], rng.choice(every_component),
                         rng.choice((2, 3)))
            next_n[issue] += 1
            _insert(conn, spec, rng)

            if outcome == "draft":
                steps = _steps(rows, moment())
            elif outcome == "in_review_r1":
                r1_in = back(end, 0, 6)
                steps = _steps(rows, back(r1_in, 0, 3), r1_in)
            elif outcome == "in_review_r2":
                r1_at = back(end, 0, 12)
                r1_in = back(r1_at, *P.R1_DAYS)
                steps = _steps(rows, back(r1_in, 0, 3), r1_in, (r1_at, "pass"))
            elif outcome in ("revise_r1", "reject_r1"):
                r1_at = moment()
                r1_in = back(r1_at, *P.R1_DAYS)
                steps = _steps(rows, back(r1_in, 0, 3), r1_in, (r1_at, outcome.split("_")[0]))
            else:   # approved, revise_r2, reject_r2: both rounds decided
                r2_at = moment()
                r1_at = back(r2_at, *P.R2_DAYS)
                r1_in = back(r1_at, *P.R1_DAYS)
                verdict = "pass" if outcome == "approved" else outcome.split("_")[0]
                steps = _steps(rows, back(r1_in, 0, 3), r1_in, (r1_at, "pass"), (r2_at, verdict))
            _walk(conn, spec.id, steps)


def answer_keys(conn) -> dict[str, AnswerKey]:
    """The key of every approved question, real or sample."""
    initial_b = settings()["elo"]["initial_b"]
    keys = {}
    for row in conn.execute("select id, options, difficulty_label from question where status = 'approved'"):
        correct = next(o["key"] for o in row["options"] if o["is_correct"])
        keys[row["id"]] = AnswerKey(correct, tuple(o["key"] for o in row["options"] if not o["is_correct"]),
                                    initial_b[row["difficulty_label"]])
    return keys
