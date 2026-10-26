"""Log records of the sample cohort that no service is asked to produce: chat turns and error reports.

A chat turn here is a row as the chat pipeline would have logged it, with placeholder text. No model
is called and nothing is retrieved.
"""
import random
from datetime import datetime, timedelta

from psycopg.types.json import Jsonb

from app import events
from app.config import settings
from seed.cohort import params as P
from seed.cohort.people import Sim

QUESTION, ANSWER = "Câu hỏi mẫu", "Câu trả lời mẫu"


def chat_turn(conn, sim: Sim, at: datetime, rng: random.Random) -> None:
    pid = sim.learner["pseudonym_id"]
    session_id = conn.execute(
        """insert into chat_session(learner_pid, title, kind, created_at, updated_at)
           values (%s, %s, 'chat', %s, %s) returning id""", (pid, QUESTION, at, at)).fetchone()["id"]
    conn.execute(
        """insert into chat_message(session_id, role, text, is_synthetic, created_at)
           values (%s, 'user', %s, true, %s)""", (session_id, QUESTION, at))

    state = rng.choices(list(P.CHAT_STATES), weights=list(P.CHAT_STATES.values()))[0]
    answered = state == "answered"
    cfg = settings()
    median_ms, sigma = P.LATENCY_MS
    latency_ms = int(rng.lognormvariate(0, sigma) * median_ms)
    conn.execute(
        """insert into chat_message(session_id, role, text, state, format, citations, claims_checked, claims_removed,
             model_version, prompt_version, corpus_version, latency_ms, is_synthetic, created_at)
           values (%s, 'assistant', %s, %s, %s, %s, %s, %s, %s, 'sample', %s, %s, true, %s)""",
        (session_id, ANSWER, state, "text" if answered else None, Jsonb([]) if answered else None,
         rng.randint(*P.CLAIMS) if answered else None,
         (1 if rng.random() < P.ANSWER_LOSES_A_CLAIM else 0) if answered else None,
         cfg["gateway"]["models"]["answer"]["id"], cfg["corpus_version"], latency_ms,
         at + timedelta(milliseconds=latency_ms)))
    events.record(conn, pid, "chat_turn", at, ref_type="chat_session", ref_id=session_id)


def write_error_reports(conn, visits: dict[str, list[datetime]], end: datetime, rng: random.Random) -> None:
    """Error reports from learners who are still there, at moments they were using the app. Three are
    left open and dated more than 14 days back when the cohort is old enough to have them."""
    moments = [(pid, at) for pid, times in sorted(visits.items()) for at in times]
    if not moments:
        return
    wanted = max(3, round(len(moments) * P.REPORT_PER_VISIT))
    chosen = rng.sample(moments, wanted) if wanted <= len(moments) else rng.choices(moments, k=wanted)
    sample_questions = [r["id"] for r in conn.execute(
        "select id from question where is_synthetic and status = 'approved' order by id")]

    old = [(pid, end - timedelta(days=rng.uniform(15, 27))) for pid, times in sorted(visits.items())
           if times and min(times) < end - timedelta(days=27)][:3]
    reports = [(pid, at, "open") for pid, at in old]
    reports += [(pid, at, "resolved" if rng.random() < P.REPORT_RESOLVED else "open")
                for pid, at in chosen[:wanted - len(old)]]

    for pid, at, status in reports:
        answers = [r["id"] for r in conn.execute(
            """select m.id from chat_message m join chat_session s on s.id = m.session_id
               where s.learner_pid = %s and m.role = 'assistant' and m.created_at <= %s order by m.id""", (pid, at))]
        about_answer = bool(answers) and rng.random() < 0.3
        conn.execute(
            """insert into error_report(target_type, target_id, reason, learner_pid, status, created_at)
               values (%s, %s, %s, %s, %s, %s)""",
            ("answer" if about_answer else "question",
             str(rng.choice(answers)) if about_answer else rng.choice(sample_questions),
             rng.choice(P.REPORT_REASONS), pid, status, at))
