"""The sample cohort's schools, activation codes and learners.

A learner comes into being the way a real one does: an activation code is issued to a school, the
code is activated, consent is given. Only the flag `is_synthetic` and the backdated clock differ.
"""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.auth.secrets import hash_code
from app.config import settings
from app.repo import learners as learner_repo
from app.services import account, auth
from seed.cohort import params as P

MIN_LEARNERS = 12


@dataclass
class Sim:
    """A synthetic learner and what the simulation knows about them that the product does not."""
    learner: dict                    # the learner row, is_synthetic already true
    index: int                       # place in the cohort: what the learner's random draws are keyed on
    ability: float                   # hidden, on the Elo scale; rises a little with every answer
    days_per_week: float
    recall: float                    # chance of recalling a card
    activated_at: datetime
    research: bool                   # gave the research consent
    drops_at: datetime | None = None        # stops studying for good
    withdraws_at: datetime | None = None    # withdraws the research consent
    leaves_at: datetime | None = None       # deletes the account


def local_time(day, hour: float) -> datetime:
    """That hour of that local day, in UTC: the services take the clock in UTC, as the API gives it."""
    zone = ZoneInfo(settings()["local_timezone"])
    return (datetime(day.year, day.month, day.day, tzinfo=zone) + timedelta(hours=hour)).astimezone(timezone.utc)


def school_sizes(n_learners: int) -> list[int]:
    """Learners per school, in the order of `SCHOOLS` and then the small school."""
    if n_learners < MIN_LEARNERS:
        raise ValueError(f"a cohort needs at least {MIN_LEARNERS} learners, so that every school has one")
    small = min(P.SMALL_SCHOOL[3], n_learners // 3)
    rest = n_learners - small
    total_weight = sum(school[3] for school in P.SCHOOLS)
    sizes = [max(1, round(rest * school[3] / total_weight)) for school in P.SCHOOLS]
    sizes[0] += rest - sum(sizes)
    return sizes + [small]


def enrol(conn, n_learners: int, start: datetime, end: datetime, reviewers: tuple[int, int], seed: int) -> list[Sim]:
    weeks = max(1, (end - start).days // 7)
    schools = [(*school[:3], school[4], school[5]) for school in P.SCHOOLS]
    schools.append((*P.SMALL_SCHOOL[:3], P.SMALL_SCHOOL[4], P.SMALL_SCHOOL[5]))
    # In a short window the learners still need time to do something after activating.
    mean_delay = min(P.ACTIVATION_DELAY_DAYS, (end - start).days / 4)
    latest = end - timedelta(days=1)

    planned = []    # (activation time, index, code, research consent)
    index = 0
    for (code, name, region, activation_rate, join_week), size in zip(schools, school_sizes(n_learners)):
        rng = P.rng_for(seed, "school", code)
        joined = start + timedelta(weeks=min(join_week, weeks // 2))
        organisation_id = conn.execute(
            "insert into organisation(code, name, region, is_synthetic) values (%s, %s, %s, true) returning id",
            (code, name, region)).fetchone()["id"]
        batch_id = conn.execute(
            "insert into import_batch(created_by, created_at, status) values (%s, %s, 'confirmed') returning id",
            (reviewers[0], joined)).fetchone()["id"]
        for n in range(round(size / activation_rate)):
            activation_code = f"{P.SAMPLE_PREFIX}{rng.getrandbits(48):012X}"
            conn.execute(
                """insert into activation_code(code_hash, batch_id, organisation_id, audience, issued_at)
                   values (%s, %s, %s, %s, %s)""",
                (hash_code(activation_code), batch_id, organisation_id,
                 "student" if rng.random() < P.STUDENT_SHARE else "graduate", joined))
            if n < size:    # the others are issued and never used
                day = (joined + timedelta(days=rng.expovariate(1 / mean_delay))).astimezone(
                    ZoneInfo(settings()["local_timezone"])).date()
                at = min(max(local_time(day, rng.uniform(*P.VISIT_HOURS)), joined), latest)
                planned.append((at, index, activation_code, rng.random() < P.RESEARCH_CONSENT))
                index += 1

    sims = []
    version = settings()["consent"]["version"]
    for at, index, activation_code, research in sorted(planned):
        rng = P.rng_for(seed, "learner", index)
        auth.activate(conn, activation_code, "cohort", at)
        learner_id = conn.execute("select learner_id from activation_code where code_hash = %s",
                                  (hash_code(activation_code),)).fetchone()["learner_id"]
        conn.execute("update learner set is_synthetic = true, created_at = %s where id = %s", (at, learner_id))
        account.give_consent(conn, learner_id, version, True, research, at + timedelta(minutes=1))

        ability = rng.gauss(0, P.ABILITY_SD)
        rank = min(1.0, max(0.0, (ability + 2) / 4))
        sim = Sim(learner=learner_repo.get(conn, learner_id), index=index, ability=ability,
                  days_per_week=rng.uniform(*P.DAYS_PER_WEEK),
                  recall=P.RECALL[0] + rank * (P.RECALL[1] - P.RECALL[0]), activated_at=at, research=research)
        week = 1
        while at + timedelta(weeks=week) < end:
            if rng.random() < P.WEEKLY_DROPOUT:
                sim.drops_at = at + timedelta(weeks=week)
                break
            week += 1
        sims.append(sim)

    _plan_departures(sims, start, end, P.rng_for(seed, "departures"))
    return sims


def _plan_departures(sims: list[Sim], start: datetime, end: datetime, rng: random.Random) -> None:
    """Who deletes their account and who withdraws the research consent, and when: in the last third
    of the window, or half-way through their own time if they joined later than that."""

    def moment(sim: Sim) -> datetime:
        earliest = max(sim.activated_at + timedelta(days=1), end - (end - start) / 3)
        if earliest >= end - timedelta(hours=2):
            return sim.activated_at + (end - sim.activated_at) / 2
        return earliest + (end - timedelta(hours=1) - earliest) * rng.random()

    leavers = rng.sample(sims, max(1, round(len(sims) * P.DELETE_SHARE)))
    for sim in leavers:
        sim.leaves_at = moment(sim)
    staying_with_consent = [s for s in sims if s.research and s.leaves_at is None]
    for sim in rng.sample(staying_with_consent, min(len(staying_with_consent),
                                                    max(1, round(len(sims) * P.WITHDRAW_SHARE)))):
        sim.withdraws_at = moment(sim)
