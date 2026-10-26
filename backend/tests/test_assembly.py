"""Exam assembly: pure, deterministic selection from the learner's history and Elo."""
from datetime import datetime, timedelta, timezone

import pytest

from app.engine.assembly import Candidate, allocate, assemble

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
MIX = {"new": 0.5, "wrong": 0.3, "review": 0.2}


def cand(i, topic="A", bucket="new", p=0.7, days=None):
    return Candidate(id=f"q{i:02d}", topic=topic, bucket=bucket, p_correct=p,
                     last_seen=None if days is None else T0 + timedelta(days=days))


def pool(new=0, wrong=0, review=0, topic="A", start=0):
    out, i = [], start
    for bucket, count in (("new", new), ("wrong", wrong), ("review", review)):
        for _ in range(count):
            out.append(cand(i, topic, bucket, days=None if bucket == "new" else i))
            i += 1
    return out


# ---- allocate: shares → whole numbers, never above what is available ----

def test_allocate_uses_largest_remainders():
    shares = {"DT.01": 0.20, "DT.02": 0.15, "DT.03": 0.15, "DT.04": 0.15, "TC.01": 0.20, "TC.02": 0.15}
    caps = {k: 9 for k in shares}
    assert allocate(shares, 10, caps) == {"DT.01": 2, "DT.02": 2, "DT.03": 2, "DT.04": 1, "TC.01": 2, "TC.02": 1}


def test_allocate_respects_caps_and_hands_the_rest_to_others():
    assert allocate({"A": 0.5, "B": 0.5}, 10, {"A": 2, "B": 20}) == {"A": 2, "B": 8}
    assert allocate({"A": 0.5, "B": 0.5}, 10, {"A": 3, "B": 4}) == {"A": 3, "B": 4}
    assert allocate({"A": 1.0, "B": 0.0}, 4, {"A": 9, "B": 9}) == {"A": 4, "B": 0}


# ---- the mix of new / previously wrong / review questions ----

def test_mix_is_five_new_three_wrong_two_review_when_available():
    plan = assemble(pool(new=10, wrong=10, review=10), 10, {"A": 1.0}, MIX, 0.7)
    assert plan.composition == {"new": 5, "wrong": 3, "review": 2}
    assert len(plan.question_ids) == len(set(plan.question_ids)) == 10


def test_first_exam_is_all_new_questions():
    plan = assemble(pool(new=20), 10, {"A": 1.0}, MIX, 0.7)
    assert plan.composition == {"new": 10, "wrong": 0, "review": 0}


def test_a_missing_bucket_is_made_up_from_the_others():
    plan = assemble(pool(new=20, wrong=1), 10, {"A": 1.0}, MIX, 0.7)
    assert plan.composition == {"new": 9, "wrong": 1, "review": 0}
    plan = assemble(pool(new=2, wrong=3, review=20), 10, {"A": 1.0}, MIX, 0.7)
    assert plan.composition == {"new": 2, "wrong": 3, "review": 5}


# ---- which question inside a bucket ----

def test_new_questions_are_chosen_by_elo_fit():
    cands = [cand(1, p=0.95), cand(2, p=0.72), cand(3, p=0.30), cand(4, p=0.66), cand(5, p=0.50)]
    plan = assemble(cands, 2, {"A": 1.0}, MIX, 0.7)
    assert sorted(plan.question_ids) == ["q02", "q04"]  # closest to a 70% chance of a correct answer


def test_wrong_and_review_questions_come_back_oldest_first():
    cands = [cand(1, bucket="wrong", days=9), cand(2, bucket="wrong", days=1), cand(3, bucket="wrong", days=5),
             cand(4, bucket="review", days=8), cand(5, bucket="review", days=2)]
    plan = assemble(cands, 3, {"A": 1.0}, {"new": 0.0, "wrong": 0.67, "review": 0.33}, 0.7)
    assert sorted(plan.question_ids) == ["q02", "q03", "q05"]


# ---- topics ----

def test_topic_shares_decide_how_many_questions_each_topic_gets():
    cands = pool(new=10, topic="A") + pool(new=10, topic="B", start=100)
    plan = assemble(cands, 10, {"A": 0.7, "B": 0.3}, MIX, 0.7)
    assert plan.topics == {"A": 7, "B": 3}


def test_topic_without_enough_questions_is_topped_up_from_another():
    cands = pool(new=2, topic="A") + pool(new=10, topic="B", start=100)
    plan = assemble(cands, 10, {"A": 0.5, "B": 0.5}, MIX, 0.7)
    assert plan.topics == {"A": 2, "B": 8}


def test_topic_balance_wins_over_the_mix():
    # Topic B only has review questions; it still gets its share.
    cands = pool(new=10, topic="A") + pool(review=10, topic="B", start=100)
    plan = assemble(cands, 10, {"A": 0.5, "B": 0.5}, MIX, 0.7)
    assert plan.topics == {"A": 5, "B": 5}


# ---- general properties ----

def test_same_input_gives_the_same_exam():
    cands = pool(new=8, wrong=5, review=5, topic="A") + pool(new=6, wrong=2, review=3, topic="B", start=100)
    shares = {"A": 0.6, "B": 0.4}
    first = assemble(cands, 10, shares, MIX, 0.7)
    again = assemble(list(reversed(cands)), 10, shares, MIX, 0.7)
    assert first.question_ids == again.question_ids


def test_small_pool_gives_every_question_once():
    plan = assemble(pool(new=3, wrong=1), 10, {"A": 1.0}, MIX, 0.7)
    assert sorted(plan.question_ids) == ["q00", "q01", "q02", "q03"]


def test_topic_missing_from_the_shares_can_still_fill_a_gap():
    cands = pool(new=3, topic="A") + pool(new=5, topic="Z", start=100)
    plan = assemble(cands, 6, {"A": 1.0}, MIX, 0.7)
    assert plan.topics == {"A": 3, "Z": 3}


# ---- topic shares: blueprint weight x weakness (Elo) x completed content ----

from app.engine.assembly import topic_shares  # noqa: E402
from app.engine.priority import TopicState  # noqa: E402


def state(code, weight=0.2, mastery=None):
    return TopicState(code, code, weight, "m", mastery)


def test_weaker_topic_gets_a_larger_share():
    shares = topic_shares([state("WEAK", mastery=0.2), state("STRONG", mastery=0.8)], set(), 0.5, 0.5)
    assert shares["WEAK"] == pytest.approx(4 * shares["STRONG"])


def test_unassessed_topic_counts_as_neutral():
    shares = topic_shares([state("NEW"), state("MID", mastery=0.5)], set(), 0.5, 0.5)
    assert shares["NEW"] == pytest.approx(shares["MID"])


def test_completed_content_weighs_double_the_unstudied():
    shares = topic_shares([state("DONE"), state("TODO")], {"DONE"}, 0.5, 0.5)
    assert shares["DONE"] == pytest.approx(2 * shares["TODO"])


def test_blueprint_weight_scales_the_share():
    shares = topic_shares([state("BIG", weight=0.3), state("SMALL", weight=0.1)], set(), 0.5, 0.5)
    assert shares["BIG"] == pytest.approx(3 * shares["SMALL"])


def test_mastered_topic_still_gets_a_small_share():
    assert topic_shares([state("ACE", mastery=1.0)], {"ACE"}, 0.5, 0.5)["ACE"] > 0
