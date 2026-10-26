"""One synthetic learner's history, written by the real services with a backdated clock.

Nothing here writes a learning record itself. The simulation only decides what the learner does:
which days they study, what they answer, how they rate a card. Home, the daily session, practice
sets, units, cards and exams then do what they do for anyone.
"""
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.auth.principal import Principal
from app.config import settings
from app.engine.elo import p_correct
from app.services import account, cards, exams, home, practice, session, units
from seed.cohort import logs
from seed.cohort import params as P
from seed.cohort.bank import AnswerKey
from seed.cohort.people import Sim, local_time

# delete_account never reads the token family of a principal; this one belongs to no device.
NO_FAMILY = "00000000-0000-0000-0000-000000000000"


class _DayOver(Exception):
    """The clock reached the end of the cohort's window: the learner stops where they are."""


class _Clock:
    def __init__(self, now: datetime, end: datetime):
        self.now, self.end = now, end

    def tick(self, seconds: float) -> datetime:
        self.now += timedelta(seconds=seconds)
        if self.now >= self.end:
            raise _DayOver
        return self.now


class _Learner:
    """The simulation's side of one learner: how they answer."""

    def __init__(self, sim: Sim, keys: dict[str, AnswerKey], seed: int, rng: random.Random):
        self.sim, self.keys, self.seed, self.rng = sim, keys, seed, rng
        self.row = sim.learner
        self._hidden_b: dict[str, float] = {}

    def _b(self, question_id: str) -> float:
        """The item's real difficulty, hidden from the product: the same for every learner."""
        if question_id not in self._hidden_b:
            noise = P.rng_for(self.seed, "b", question_id).gauss(0, P.B_NOISE_SD)
            self._hidden_b[question_id] = self.keys[question_id].label_b + noise
        return self._hidden_b[question_id]

    def choose(self, question_id: str) -> str:
        key = self.keys[question_id]
        correct = self.rng.random() < p_correct(self.sim.ability, self._b(question_id))
        self.sim.ability += P.LEARN_RATE
        return key.correct if correct else self.rng.choice(key.wrong)

    def item_ms(self) -> int:
        return self.rng.randint(*P.ITEM_MS)


def _cards(conn, who: _Learner, step: dict, clock: _Clock) -> None:
    for card in cards.due(conn, who.row, step["count"], clock.now)["items"]:
        time_ms = who.rng.randint(*P.CARD_MS)
        cards.review(conn, who.row, card["id"], 3 if who.rng.random() < who.sim.recall else 1,
                     clock.tick(time_ms / 1000), time_ms)


def _practice(conn, who: _Learner, set_id: int, clock: _Clock) -> None:
    for item in practice.view(conn, who.row, set_id)["items"]:
        if item["chosen"] is None:
            time_ms = who.item_ms()
            practice.answer(conn, who.row, set_id, item["question_id"], who.choose(item["question_id"]),
                            clock.tick(time_ms / 1000), time_ms)
    practice.complete(conn, who.row, set_id, clock.tick(5))


def _unit(conn, who: _Learner, unit_id: str, clock: _Clock) -> None:
    view = units.next_item(conn, who.row, unit_id, clock.now)
    for _ in range(P.UNIT_ITEMS_PER_DAY):
        if view["done"]:
            return
        item = view["item"]
        time_ms = who.item_ms()
        answered_at = clock.tick(time_ms / 1000)        # reading a content card takes time too
        if item["kind"] == "quiz" and item["chosen"] is None:
            units.answer(conn, who.row, unit_id, item["unit_item_id"], who.choose(item["question"]["id"]),
                         answered_at, time_ms)
        view = units.advance(conn, who.row, unit_id, item["unit_item_id"], clock.tick(5))


def _mock(conn, who: _Learner, clock: _Clock) -> bool:
    """Sit the sample mock, if the whole attempt fits before the end of the window."""
    limit = 40 * P.SECONDS_PER_QUESTION
    if clock.now + timedelta(seconds=limit + 60) >= clock.end:
        return False
    started = clock.tick(30)
    view = exams.start(conn, who.row, P.SAMPLE_FORM_ID, False, started)
    questions = sorted(q["id"] for q in view["questions"])      # the service shuffles them; the draws must not depend on that
    duration = len(questions) * P.SECONDS_PER_QUESTION * who.rng.uniform(*P.MOCK_PACE)
    for i, question_id in enumerate(questions, start=1):
        chosen = who.choose(question_id)
        if who.rng.random() >= P.BLANK_RATE:
            exams.save_answer(conn, who.row, view["attempt_id"], question_id, chosen, False,
                              started + timedelta(seconds=duration * i / (len(questions) + 1)))
    clock.now = started + timedelta(seconds=duration)
    exams.submit(conn, who.row, view["attempt_id"], clock.now)
    return True


def _study(conn, who: _Learner, clock: _Clock, mock_due: bool) -> bool:
    """One visit. Returns whether a mock was sat."""
    home.home(conn, who.row, clock.now)
    for step in session.today(conn, who.row, clock.tick(20))["steps"]:
        if step["done"]:
            continue
        if step["kind"] == "cards":
            _cards(conn, who, step, clock)
        elif step["kind"] == "practice" and who.rng.random() < P.PRACTICE_STEP:
            _practice(conn, who, step["practice_set_id"], clock)
        elif step["kind"] == "continue" and who.rng.random() < P.UNIT_STEP:
            _unit(conn, who, step["unit_id"], clock)
    if who.rng.random() < P.CHAT_PER_VISIT:
        logs.chat_turn(conn, who.sim, clock.tick(who.rng.uniform(60, 300)), who.rng)
    return mock_due and _mock(conn, who, clock)


def history_rng(seed: int, sim: Sim):
    """The draws of one learner's history, keyed on their place in the cohort. Not on the pseudonym:
    it comes from a database sequence that a reset does not restart, so the same seed would give
    another history on a database that has seen an activation before."""
    return P.rng_for(seed, "history", sim.index)


def run_learner(conn, sim: Sim, keys: dict[str, AnswerKey], end: datetime, seed: int) -> list[datetime]:
    """Live this learner's days from activation to the end of the window (or to the day they leave),
    committing after each. Returns when their visits began."""
    learner = sim.learner
    rng = history_rng(seed, sim)
    who = _Learner(sim, keys, seed, rng)
    zone = ZoneInfo(settings()["local_timezone"])
    first_day = sim.activated_at.astimezone(zone).date()
    last_day = end.astimezone(zone).date()
    next_mock = first_day + timedelta(days=rng.randint(0, P.FIRST_MOCK_WITHIN_DAYS))
    visits: list[datetime] = []
    withdrawn = False

    day = first_day
    while day <= last_day:
        begins = max(local_time(day, rng.uniform(*P.VISIT_HOURS)), sim.activated_at + timedelta(minutes=5))
        if sim.leaves_at and sim.leaves_at <= begins:
            account.delete_account(conn, Principal("learner", learner["id"], "learner", NO_FAMILY,
                                                   learner["pseudonym_id"]), sim.leaves_at)
            conn.commit()
            return visits
        if sim.withdraws_at and not withdrawn and sim.withdraws_at <= begins:
            account.withdraw_consent(conn, learner["id"], "research", sim.withdraws_at)
            withdrawn = True
        dropped = sim.drops_at is not None and begins >= sim.drops_at
        studies = day == first_day or rng.random() < sim.days_per_week / 7
        if studies and not dropped and begins < end:
            clock = _Clock(begins, min(end, sim.leaves_at or end))     # nothing happens after an account is deleted
            visits.append(begins)
            try:
                if _study(conn, who, clock, mock_due=day >= next_mock):
                    next_mock = day + timedelta(days=rng.randint(*P.MOCK_EVERY_DAYS))
            except _DayOver:
                pass
        conn.commit()
        day += timedelta(days=1)

    # A departure planned for the last hours, after the final visit, still happens.
    if sim.leaves_at:
        account.delete_account(conn, Principal("learner", learner["id"], "learner", NO_FAMILY,
                                               learner["pseudonym_id"]), sim.leaves_at)
    elif sim.withdraws_at and not withdrawn:
        account.withdraw_consent(conn, learner["id"], "research", sim.withdraws_at)
    conn.commit()
    return visits
