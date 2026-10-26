"""One small cohort, written by the real services."""
from datetime import datetime, timezone

import pytest

from seed import cohort, run_seed
from tests.conftest import dev_learner

END = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def test_a_small_cohort_runs_through_the_real_services(conn):
    run_seed(conn)
    cohort.run(conn, learners=20, weeks=2, seed=7, end=END)

    def n(sql, *args):
        return conn.execute(f"select count(*) n from {sql}", args).fetchone()["n"]

    assert n("learner where is_synthetic") + n("deletion_request") == 20
    assert n("organisation where is_synthetic") == 6
    assert n("activation_code where organisation_id is not null and activated_at is null") > 0
    assert n("consent_record where kind = 'research'") < n("consent_record where kind = 'service'")

    # written by the services, flagged, and never dated after the end
    assert n("activity_event") > 0 and n("activity_event where not is_synthetic") == 0
    assert n("activity_event where occurred_at > %s", END) == 0
    assert n("item_response where created_at > %s", END) == 0
    assert n("exam_attempt where form_id = 'SMP-MOCK-01' and submitted_at is not null") > 0
    assert n("exam_attempt where submitted_at is null") == 0
    assert n("practice_set where completed_at is not null") > 0
    assert n("card_review") > 0

    # log records
    assert n("chat_message where role = 'assistant'") > 0 and n("chat_message where not is_synthetic") == 0
    assert n("error_report") >= 3
    assert n("question where is_synthetic and status = 'in_review_r2'") == 60

    # the dev learner was left alone
    assert n("item_response where learner_id = %s", dev_learner(conn)["id"]) == 0

    with pytest.raises(RuntimeError, match="reset-dev"):
        cohort.run(conn, learners=20, weeks=2, seed=7, end=END)


@pytest.mark.parametrize("learners,weeks", [(5, 2), (20, 0)])
def test_bad_arguments_are_refused_before_anything_is_written(conn, learners, weeks):
    """A refused run must leave no sample bank behind: with one, every later run is refused too."""
    run_seed(conn)
    with pytest.raises(ValueError):
        cohort.run(conn, learners=learners, weeks=weeks, seed=7, end=END)
    assert conn.execute("select count(*) n from question where is_synthetic").fetchone()["n"] == 0


def test_a_history_is_drawn_from_the_learners_place_in_the_cohort_not_their_pseudonym():
    """Pseudonyms come from a database sequence that a reset does not restart; a history seeded
    from one would differ from run to run."""
    from seed.cohort.people import Sim
    from seed.cohort.simulate import history_rng

    def sim(pseudonym: str) -> Sim:
        return Sim(learner={"pseudonym_id": pseudonym}, index=3, ability=0.0, days_per_week=3.0, recall=0.8,
                   activated_at=END, research=True)

    assert history_rng(7, sim("HV-001000")).random() == history_rng(7, sim("HV-009999")).random()
    assert history_rng(7, sim("HV-001000")).random() != history_rng(8, sim("HV-001000")).random()
