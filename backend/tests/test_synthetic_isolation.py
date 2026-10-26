"""A real learner never meets the sample bank; a synthetic learner's events are flagged."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from app import events
from app.errors import ApiError
from app.repo import exams as exams_repo
from app.repo import practice as practice_repo
from app.services import exams, home
from seed.blueprint import load_blueprint
from seed.cohort import bank
from seed.cohort.params import SAMPLE_FORM_ID, SAMPLE_PREFIX
from seed.dev import ensure_demo_reviewers

NOW = datetime(2026, 10, 5, 3, 0, tzinfo=timezone.utc)


def _sample(ids):
    return [i for i in ids if i.startswith(SAMPLE_PREFIX)]


def test_a_real_learner_never_meets_the_sample_bank(conn, learner):
    bank.write_core(conn, load_blueprint(), ensure_demo_reviewers(conn), NOW - timedelta(days=1), random.Random(1))

    approved = conn.execute("select count(*) n from question where is_synthetic and status = 'approved'").fetchone()["n"]
    assert approved == 48 * 11 + 6 * 6

    real = [r["question_id"] for r in practice_repo.seen(conn, learner["id"], "CI-01", synthetic=False)]
    sample = [r["question_id"] for r in practice_repo.seen(conn, learner["id"], "CI-01", synthetic=True)]
    assert not _sample(real) and _sample(sample)
    assert not _sample(r["id"] for r in exams_repo.candidate_rows(conn, learner["id"], synthetic=False))

    assert SAMPLE_FORM_ID not in [f["id"] for f in exams.list_forms(conn, learner, NOW)["items"]]
    assert home.home(conn, learner, NOW)["next_mock"]["form_id"] != SAMPLE_FORM_ID
    with pytest.raises(ApiError) as refused:
        exams.start(conn, learner, SAMPLE_FORM_ID, False, NOW)
    assert (refused.value.status, refused.value.code) == (404, "form_not_found")

    synthetic = {**learner, "is_synthetic": True}
    assert len(exams.start(conn, synthetic, SAMPLE_FORM_ID, False, NOW)["questions"]) == 40


def test_an_event_of_a_synthetic_learner_is_flagged(conn, learner):
    events.record(conn, learner["pseudonym_id"], "visit", NOW)
    conn.execute("update learner set is_synthetic = true where id = %s", (learner["id"],))
    events.record(conn, learner["pseudonym_id"], "visit", NOW + timedelta(hours=1))
    flags = [r["is_synthetic"] for r in conn.execute("select is_synthetic from activity_event order by id")]
    assert flags == [False, True]


def test_a_sample_passage_is_never_retrieved_or_shown(conn, learner):
    """A card needs a source, so each sample question cites a placeholder passage. That passage
    belongs to a synthetic document: search never returns it and the source sheet never shows it."""
    from app.chat.normalise import normalise
    from app.chat.retrieval import search
    from app.config import settings
    from app.repo import content
    from app.services.responses import record_response
    from tests.conftest import glossary, wrong_key

    bank.write_core(conn, load_blueprint(), ensure_demo_reviewers(conn), NOW - timedelta(days=1), random.Random(1))
    sample_passages = conn.execute(
        "select count(*) n from passage p join document d on d.id = p.document_id where d.is_synthetic").fetchone()["n"]
    assert sample_passages == 54

    hits = search(conn, normalise("Tài liệu mẫu, đoạn mẫu", glossary(conn)), settings()["retrieval"]["top_k"], 0.0)
    assert not _sample(h.id for h in hits)
    assert content.passage_view(conn, f"{SAMPLE_PREFIX}P-01") is None

    # the card rule works on a sample question: a wrong answer makes a card with a citation
    question = content.approved_question(conn, f"{SAMPLE_PREFIX}01-001")
    result = record_response(conn, {**learner, "is_synthetic": True}, question, wrong_key(conn, question["id"]),
                             "practice", NOW)
    card = conn.execute("select citation from card where id = %s", (result.card_id,)).fetchone()
    assert card["citation"] == "Tài liệu mẫu, tr. 1"


def test_a_real_learners_progress_and_searched_list_never_name_the_sample_bank(conn, learner):
    """Two queries written after the sample bank existed: the topics Tiến độ may prioritise, and the
    documents "Đã tìm ở:" lists when nothing was found."""
    from app.repo import content
    from app.repo import progress as progress_repo

    real_topics = progress_repo.topics_with_questions(conn, synthetic=False)
    bank.write_core(conn, load_blueprint(), ensure_demo_reviewers(conn), NOW - timedelta(days=1), random.Random(1))
    assert progress_repo.topics_with_questions(conn, synthetic=False) == real_topics          # the bank adds none
    assert len(progress_repo.topics_with_questions(conn, synthetic=True)) > len(real_topics)  # but a sample learner has them
    assert "Tài liệu mẫu" not in [d["title"] for d in content.documents_in_scope(conn, None)]
