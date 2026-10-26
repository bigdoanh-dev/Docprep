"""Chat sessions and their messages. A session belongs to a pseudonym, never to a name."""
from datetime import datetime

from psycopg.types.json import Jsonb


def create_session(conn, learner_pid: str, now: datetime, *, title: str | None = None, kind: str = "chat",
                   module_id: str | None = None, question_id: str | None = None) -> int:
    return conn.execute(
        """insert into chat_session(learner_pid, title, kind, module_id, question_id, created_at, updated_at)
           values (%s, %s, %s, %s, %s, %s, %s) returning id""",
        (learner_pid, title, kind, module_id, question_id, now, now)).fetchone()["id"]


def own_session(conn, learner_pid: str, session_id: int) -> dict | None:
    """A chat session of this learner. The tutor's sessions are not reachable by id."""
    return conn.execute("select * from chat_session where id = %s and learner_pid = %s and kind = 'chat'",
                        (session_id, learner_pid)).fetchone()


def tutor_session(conn, learner_pid: str, title: str) -> dict | None:
    return conn.execute("select id from chat_session where learner_pid = %s and kind = 'tutor' and title = %s",
                        (learner_pid, title)).fetchone()


def set_title(conn, session_id: int, title: str) -> None:
    conn.execute("update chat_session set title = %s where id = %s", (title, session_id))


def add_message(conn, session_id: int, role: str, text: str, now: datetime, *, state: str | None = None,
                answer_format: str | None = None, citations: list[dict] | None = None,
                retrieved_passage_ids: list[str] | None = None, notice: str | None = None,
                model_version: str | None = None, prompt_version: str | None = None,
                corpus_version: str | None = None, latency_ms: int | None = None, tokens_in: int | None = None,
                tokens_out: int | None = None, cost: float | None = None, trace: list[dict] | None = None,
                claims_checked: int | None = None, claims_removed: int | None = None,
                clarify_options: list[dict] | None = None, searched: list[dict] | None = None,
                nearest_chapter: dict | None = None, clarifies_message_id: int | None = None) -> int:
    def json(value):
        return None if value is None else Jsonb(value)

    message_id = conn.execute(
        """insert into chat_message(session_id, role, text, state, format, citations, retrieved_passage_ids, notice,
             model_version, prompt_version, corpus_version, latency_ms, tokens_in, tokens_out, cost, created_at,
             trace, claims_checked, claims_removed, clarify_options, searched, nearest_chapter, clarifies_message_id)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           returning id""",
        (session_id, role, text, state, answer_format, json(citations),
         retrieved_passage_ids, notice, model_version, prompt_version, corpus_version, latency_ms, tokens_in,
         tokens_out, cost, now, json(trace), claims_checked, claims_removed, json(clarify_options), json(searched),
         json(nearest_chapter), clarifies_message_id)).fetchone()["id"]
    conn.execute("update chat_session set updated_at = %s where id = %s", (now, session_id))
    return message_id


def sessions(conn, learner_pid: str, before: tuple[datetime, int] | None, limit: int) -> list[dict]:
    """Titled chat sessions, newest activity first; ties broken by id so paging is stable."""
    page = "and (updated_at, id) < (%s, %s)" if before else ""
    return conn.execute(
        f"""select id, title, updated_at from chat_session
            where learner_pid = %s and kind = 'chat' and title is not null {page}
            order by updated_at desc, id desc limit %s""",
        (learner_pid, *(before or ()), limit)).fetchall()


def messages(conn, session_id: int, after_id: int, limit: int) -> list[dict]:
    return conn.execute(
        """select id, role, text, created_at, state, format, citations, notice, clarify_options, searched,
                  nearest_chapter, helpful, claims_checked, claims_removed, trace
           from chat_message where session_id = %s and id > %s order by id limit %s""",
        (session_id, after_id, limit)).fetchall()


def answer_in_session(conn, session_id: int, message_id: int) -> dict | None:
    """An assistant message of that session."""
    return conn.execute("select id, state from chat_message where id = %s and session_id = %s and role = 'assistant'",
                        (message_id, session_id)).fetchone()


def has_answer(conn, session_id: int) -> bool:
    """Whether the session already holds an assistant message."""
    return conn.execute("select 1 from chat_message where session_id = %s and role = 'assistant' limit 1",
                        (session_id,)).fetchone() is not None


def rate_answer(conn, learner_pid: str, message_id: int, helpful: bool) -> bool:
    """Set "Hữu ích" on an answer given to this learner, in chat or by the tutor. False when there is no such answer."""
    return conn.execute(
        """update chat_message m set helpful = %s from chat_session s
           where m.id = %s and m.role = 'assistant' and s.id = m.session_id and s.learner_pid = %s returning m.id""",
        (helpful, message_id, learner_pid)).fetchone() is not None
