"""The adaptation summary (handover/05-algorithms.md §13): only what a set really changed."""
from app.engine.adaptation import summarise
from app.schemas.practice import AdaptationSummary

FND = "Khái niệm cơ bản của y học dự phòng"


def test_every_line_is_reported_when_everything_happened():
    s = summarise(total=6, correct=4, competencies_answered=1, cards_created=2, tomorrow_before="CI-01", tomorrow_after="FND",
                  tomorrow_after_name=FND)
    assert s == {"graded": {"correct": 4, "total": 6}, "mastery_updated": {"competencies": 1},
                 "cards_created": {"n": 2}, "tomorrow": {"reordered": True, "top_item": FND}}
    AdaptationSummary.model_validate(s)


def test_a_perfect_set_claims_no_cards_and_no_reordering():
    s = summarise(total=6, correct=6, competencies_answered=1, cards_created=0, tomorrow_before="CI-01", tomorrow_after="CI-01",
                  tomorrow_after_name="X")
    assert s == {"graded": {"correct": 6, "total": 6}, "mastery_updated": {"competencies": 1},
                 "cards_created": None, "tomorrow": None}
    AdaptationSummary.model_validate(s)


def test_a_set_closed_without_an_answer_reports_the_grade_alone():
    s = summarise(total=6, correct=0, competencies_answered=0, cards_created=0, tomorrow_before="CI-01",
                  tomorrow_after="CI-01", tomorrow_after_name="X")
    assert s == {"graded": {"correct": 0, "total": 6}, "mastery_updated": None, "cards_created": None, "tomorrow": None}


def test_a_set_that_gives_tomorrow_its_first_practice_topic_says_so():
    s = summarise(total=6, correct=4, competencies_answered=1, cards_created=2, tomorrow_before=None,
                  tomorrow_after="FND", tomorrow_after_name=FND)
    assert s["tomorrow"] == {"reordered": True, "top_item": FND}


def test_no_tomorrow_line_when_tomorrow_has_no_practice():
    s = summarise(total=6, correct=6, competencies_answered=1, cards_created=0, tomorrow_before="FND",
                  tomorrow_after=None, tomorrow_after_name=None)
    assert s["tomorrow"] is None


def test_no_reordering_is_claimed_without_a_name_to_show():
    s = summarise(total=6, correct=1, competencies_answered=1, cards_created=5, tomorrow_before="CI-01", tomorrow_after="FND",
                  tomorrow_after_name=None)
    assert s["tomorrow"] is None and s["cards_created"] == {"n": 5}
