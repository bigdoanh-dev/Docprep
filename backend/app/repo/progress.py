"""The learner's own records, as the two progress screens read them."""
from datetime import date, datetime

from app.repo.content import ONCE_APPROVED

# ---- Năng lực ------------------------------------------------------------------------------------


def answer_counts(conn, learner_id: int) -> dict[str, dict]:
    """The learner's answers per topic, from quizzes, practice and exams alike."""
    return {r["competency_code"]: r for r in conn.execute(
        """select q.competency_code, count(*) as total, count(*) filter (where r.correct) as correct
           from item_response r join question q on q.id = r.question_id and q.version = r.question_version
           where r.learner_id = %s group by q.competency_code""", (learner_id,))}


def topics_with_questions(conn, synthetic: bool) -> set[str]:
    """The topics that have an approved question to practise. The sample bank counts for synthetic
    learners only."""
    return {r["competency_code"] for r in conn.execute(
        "select distinct competency_code from question where status = 'approved' and (not is_synthetic or %s)",
        (synthetic,))}


def weakest_units(conn, learner_id: int) -> dict[str, str]:
    """Per topic, the title of the unit in which the learner has the most wrong answers."""
    out: dict[str, str] = {}
    for r in conn.execute(
            """select u.competency_code, u.topic, count(*) as wrong
               from item_response r
               join unit_item i on i.question_id = r.question_id and i.kind = 'quiz'
               join unit u on u.id = i.unit_id
               where r.learner_id = %s and not r.correct
               group by u.competency_code, u.topic, u.module_id, u.ord
               order by wrong desc, u.module_id, u.ord""", (learner_id,)):
        out.setdefault(r["competency_code"], r["topic"])
    return out


def mock_attempts(conn, learner_id: int, limit: int | None) -> list[dict]:
    """Handed-in attempts on mock forms (not the diagnostic), newest first, with their real scores."""
    return conn.execute(
        """select a.id as attempt_id, f.title, a.submitted_at, a.score, cardinality(a.question_order) as total
           from exam_attempt a join exam_form f on f.id = a.form_id
           where a.learner_id = %s and a.submitted_at is not null and f.kind in ('mock', 'demo_short', 'assembled')
           order by a.submitted_at desc, a.id desc limit %s""", (learner_id, limit)).fetchall()


def level_counts(conn, attempt_ids: list[int]) -> dict[int, dict]:
    """Answers given in those attempts, by the Bloom band of the question version answered."""
    return {r["bloom_level"]: r for r in conn.execute(
        """select q.bloom_level, count(*) as total, count(*) filter (where r.correct) as correct
           from item_response r join question q on q.id = r.question_id and q.version = r.question_version
           where r.attempt_id = any(%s) group by q.bloom_level""", (attempt_ids,))}


# ---- Nhịp học ------------------------------------------------------------------------------------

def study_ms_by_day(conn, learner_pid: str, timezone: str, since: datetime) -> dict[date, int]:
    """Milliseconds of recorded study time per local day."""
    return {r["day"]: int(r["ms"]) for r in conn.execute(
        """select (occurred_at at time zone %s)::date as day, sum(duration_ms) as ms from activity_event
           where learner_pid = %s and occurred_at >= %s and duration_ms is not null group by 1""",
        (timezone, learner_pid, since))}


def active_days(conn, learner_pid: str, timezone: str, since: datetime, kinds: list[str]) -> set[date]:
    """Local days with at least one event of those kinds."""
    return {r["day"] for r in conn.execute(
        """select distinct (occurred_at at time zone %s)::date as day from activity_event
           where learner_pid = %s and occurred_at >= %s and kind = any(%s)""", (timezone, learner_pid, since, kinds))}


def cards(conn, learner_id: int) -> list[dict]:
    """The learner's unsuspended cards with their schedule and the topic of their question."""
    return conn.execute(
        f"""select c.id, c.fsrs_card, c.reps, c.due_at, c.created_at, q.competency_code
            from card c
            join lateral (select q.competency_code from question q
                          where q.id = c.source_question_id and {ONCE_APPROVED}
                          order by (q.status = 'approved') desc, q.version desc limit 1) q on true
            where c.learner_id = %s and not c.suspended order by c.id""", (learner_id,)).fetchall()


def review_counts(conn, learner_id: int, since: datetime) -> dict:
    return conn.execute(
        """select count(*) as reviews, count(*) filter (where r.rating >= 2) as recalled
           from card_review r join card c on c.id = r.card_id
           where c.learner_id = %s and r.reviewed_at > %s""", (learner_id, since)).fetchone()


def reviews_of(conn, card_id: int) -> list[tuple[datetime, int]]:
    return [(r["reviewed_at"], r["rating"]) for r in conn.execute(
        "select reviewed_at, rating from card_review where card_id = %s order by reviewed_at, id", (card_id,))]


# `max_ms` is the most one answer or one review counts for, the same cap the activity log applies:
# a phone left open is not study time.

def unit_activity(conn, learner_id: int, since: datetime, max_ms: int) -> list[dict]:
    return conn.execute(
        """select m.short_name, u.topic, s.done, s.updated_at as occurred_at,
                  (select sum(least(r.time_ms, %s)) filter (where r.time_ms is not null) from item_response r where r.unit_session_id = s.id) as ms
           from unit_session s join unit u on u.id = s.unit_id join module m on m.id = u.module_id
           where s.learner_id = %s and s.updated_at >= %s""", (max_ms, learner_id, since)).fetchall()


def practice_activity(conn, learner_id: int, since: datetime, max_ms: int) -> list[dict]:
    return conn.execute(
        """select p.competency_code, p.summary, p.completed_at as occurred_at,
                  (select sum(least(r.time_ms, %s)) filter (where r.time_ms is not null) from item_response r where r.practice_set_id = p.id) as ms
           from practice_set p where p.learner_id = %s and p.completed_at >= %s""", (max_ms, learner_id, since)).fetchall()


def chat_activity(conn, learner_pid: str, since: datetime) -> list[dict]:
    return conn.execute(
        """select title, updated_at as occurred_at from chat_session
           where learner_pid = %s and kind = 'chat' and title is not null and updated_at >= %s""",
        (learner_pid, since)).fetchall()


def card_activity(conn, learner_id: int, timezone: str, since: datetime, max_ms: int) -> list[dict]:
    """Card reviews grouped by local day: the cards reviewed, and how many of them were recalled
    when first shown that day (a card seen again minutes later is the same card)."""
    return conn.execute(
        """select day, count(distinct card_id) as cards, count(*) filter (where first_today and rating >= 2) as recalled,
                  sum(least(time_ms, %s)) filter (where time_ms is not null) as ms, max(reviewed_at) as occurred_at
           from (select (r.reviewed_at at time zone %s)::date as day, r.card_id, r.rating, r.time_ms, r.reviewed_at,
                        row_number() over (partition by (r.reviewed_at at time zone %s)::date, r.card_id
                                           order by r.reviewed_at, r.id) = 1 as first_today
                 from card_review r join card c on c.id = r.card_id
                 where c.learner_id = %s and r.reviewed_at >= %s) reviews
           group by day""", (max_ms, timezone, timezone, learner_id, since)).fetchall()


def exam_activity(conn, learner_id: int, since: datetime) -> list[dict]:
    return conn.execute(
        """select f.title, a.score, cardinality(a.question_order) as total, a.submitted_at as occurred_at,
                  extract(epoch from a.submitted_at - a.started_at) * 1000 as ms
           from exam_attempt a join exam_form f on f.id = a.form_id
           where a.learner_id = %s and a.submitted_at >= %s""", (learner_id, since)).fetchall()
