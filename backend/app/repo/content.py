"""Questions, learning content, sources and the topic tree, as the learner flows read them."""


def approved_question(conn, question_id: str) -> dict | None:
    """The approved version of a question: the only one a learner may be served."""
    return conn.execute("select * from question where id = %s and status = 'approved'", (question_id,)).fetchone()


# A version a learner may still see after its retirement: it is approved, or it was approved once.
# A draft, a version in review or a rejected one never qualifies, whatever its number.
ONCE_APPROVED = """(q.status = 'approved' or (q.status = 'retired' and exists (
    select 1 from status_transition t where t.target_type = 'question' and t.target_id = q.id
      and t.version = q.version and t.to_status = 'approved')))"""


def question_as_served(conn, question_id: str, version: int | None) -> dict | None:
    """The question as the learner was served it, for work already started: an attempt, an answer.

    With the version recorded at the time, that version, even if it was retired since. Without one
    (work recorded before versions were kept): the approved version, else the latest retired one.
    Never a version that was not approved: a newer draft is not shown in its place."""
    if version is not None:
        return conn.execute(f"select q.* from question q where q.id = %s and q.version = %s and {ONCE_APPROVED}",
                            (question_id, version)).fetchone()
    return conn.execute(
        f"""select q.* from question q where q.id = %s and {ONCE_APPROVED}
            order by (q.status = 'approved') desc, q.version desc limit 1""", (question_id,)).fetchone()


def lock_questions(conn, question_ids: list[str]) -> None:
    """Lock those questions' rows in a fixed order. Scoring an exam updates the statistics of every
    answered question in one transaction; two hand-ins that took the rows in their own shuffled
    order would wait on each other."""
    conn.execute("select 1 from question where id = any(%s) order by id, version for update", (question_ids,))


def approved_content(conn, content_id: str) -> dict | None:
    return conn.execute("select * from content_item where id = %s and status = 'approved'", (content_id,)).fetchone()


def citations_for(conn, passage_ids: list[str]) -> list[dict]:
    """Citation fields for those passages. `n` is the position in the list given; an unknown id is skipped."""
    rows = {r["passage_id"]: r for r in conn.execute(
        """select p.id as passage_id, d.title as document, p.chapter, p.section, p.page_start as page, p.article
           from passage p join document d on d.id = p.document_id where p.id = any(%s)""", (passage_ids,))}
    return [{"n": n, **rows[pid]} for n, pid in enumerate(passage_ids, start=1) if pid in rows]


def passage_source(conn, passage_id: str) -> dict | None:
    """Where a passage is in its document, for a card's citation line."""
    return conn.execute(
        """select p.page_start, p.article, d.title from passage p join document d on d.id = p.document_id
           where p.id = %s""", (passage_id,)).fetchone()


def passage_view(conn, passage_id: str) -> dict | None:
    """A source as the learner may see it: an excerpt within the document's limit, never the full text.
    A placeholder passage of the sample bank is not a source and is not shown."""
    row = conn.execute(
        """select p.id, d.title as document, p.chapter, p.section, p.page_start as page, p.article, p.text,
                  d.excerpt_limit, d.demo_label, d.validity_note
           from passage p join document d on d.id = p.document_id
           where p.id = %s and not d.is_synthetic""", (passage_id,)).fetchone()
    if row is None:
        return None
    text, limit = row.pop("text"), row.pop("excerpt_limit")
    row["excerpt"] = text if not limit or len(text) <= limit else text[:limit].rstrip() + "…"
    return row


def topics(conn) -> list[dict]:
    """The topics mastery and priority are kept on: the competency nodes with no child, each with
    its blueprint weight and the học phần that teaches it."""
    return conn.execute(
        """select n.code, n.name, n.blueprint_weight as weight,
                  (select m.id from module m where n.code = any(m.competency_codes) order by m.ord limit 1) as module_id
           from competency_node n
           where not exists (select 1 from competency_node c where c.parent_code = n.code)
           order by n.code""").fetchall()


_DONE_UNITS = "select distinct unit_id from unit_session where learner_id = %s and done"
_OPEN_UNITS = "select distinct unit_id from unit_session where learner_id = %s and not done"


def modules(conn, learner_id: int) -> list[dict]:
    """Every học phần in order, with the learner's progress and what the list filters on."""
    return conn.execute(
        f"""select m.id, m.name, m.short_name, m.core_issue_group_id as core_issue_group, m.coming_soon,
                   m.competency_codes,
                   (select count(*) from unit u where u.module_id = m.id) as units_total,
                   (select count(*) from unit u where u.module_id = m.id and u.id in ({_DONE_UNITS})) as units_done,
                   (select count(*) from unit u where u.module_id = m.id and u.id in ({_OPEN_UNITS})) as units_open,
                   (select count(*) from core_issue i where i.group_id = m.core_issue_group_id) as topics_total,
                   array(select distinct q.bloom_level from question q
                         where q.status = 'approved' and q.competency_code = any(m.competency_codes)
                           and (not q.is_synthetic or (select is_synthetic from learner where id = %s))) as bloom_levels
            from module m order by m.ord""", (learner_id, learner_id, learner_id)).fetchall()


def module(conn, module_id: str) -> dict | None:
    return conn.execute("select id, name, short_name from module where id = %s", (module_id,)).fetchone()


def units_of(conn, learner_id: int, module_id: str) -> list[dict]:
    return conn.execute(
        f"""select u.id, u.topic, u.id in ({_DONE_UNITS}) as done from unit u
            where u.module_id = %s order by u.ord""", (learner_id, module_id)).fetchall()


def module_short_names(conn) -> dict[str, str]:
    return {m["id"]: m["short_name"] for m in conn.execute("select id, short_name from module")}


def remediation_for(conn, question_id: str, competency_code: str) -> dict | None:
    """The worked example to show after a wrong answer: the one written for that question in a unit
    (`specific`), else the first one of a unit on the same competency. Approved content only."""
    return conn.execute(
        """select c.title, c.body, c.source_passage_ids, i.id as unit_item_id,
                  coalesce(quiz.question_id = %(question)s, false) as specific
           from unit_item i
           join unit u on u.id = i.unit_id
           join content_item c on c.id = i.content_id and c.status = 'approved'
           left join unit_item quiz on quiz.id = i.after_item_id
           where i.kind = 'remediation' and (quiz.question_id = %(question)s or u.competency_code = %(code)s)
           order by coalesce(quiz.question_id = %(question)s, false) desc, u.module_id, u.ord, u.id, i.ord limit 1""",
        {"question": question_id, "code": competency_code}).fetchone()


def glossary(conn) -> list[dict]:
    """The approved glossary: terms with their synonyms, and which terms experts flagged as ambiguous."""
    return conn.execute(
        "select term, synonyms, ambiguous, sense_group from glossary_term where status = 'approved' order by id").fetchall()


def documents_in_scope(conn, module_id: str | None) -> list[dict]:
    """The documents retrieval looks in: all of them, or those with a passage of the học phần. Each
    with the pages its passages span. A document of the sample bank is never searched, so never listed."""
    scope = "and p.competency_code = any(select unnest(competency_codes) from module where id = %s)" if module_id else ""
    return conn.execute(
        f"""select d.title, min(p.page_start) as first_page, max(p.page_start) as last_page
            from passage p join document d on d.id = p.document_id where not d.is_synthetic {scope}
            group by d.id, d.title order by d.title""", (module_id,) if module_id else ()).fetchall()
