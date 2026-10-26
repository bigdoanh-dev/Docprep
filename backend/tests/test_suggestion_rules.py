"""Which suggestions follow a chat answer (handover/04, "Suggestions after an answer"): pure, from the
learner's own record; nothing here is a model's doing."""
from app.engine import suggestions

NAMES = {"FND": "Khái niệm cơ bản của y học dự phòng", "CI-04": "Tiêm phòng/Tiêm chủng trẻ em và người lớn"}


def propose(**kw):
    base = dict(cited=["CI-04"], wrong={"CI-04": 2}, available={"CI-04": 5}, names=NAMES, tomorrow_taken=False,
                window_days=14, max_items=3)
    return suggestions.propose(**{**base, **kw})


def test_a_weak_spot_the_answer_touches_gives_two_offers():
    reason = "Bạn đã trả lời sai 2 câu về Tiêm phòng/Tiêm chủng trẻ em và người lớn trong 14 ngày qua."
    assert propose() == [
        {"kind": "practise", "competency_code": "CI-04", "n_items": 3, "label_vi": "Luyện 3 câu đã duyệt", "reason_vi": reason},
        {"kind": "add_to_tomorrow", "competency_code": "CI-04", "n_items": None, "label_vi": "Thêm vào phiên ngày mai",
         "reason_vi": reason}]


def test_nothing_is_offered_without_a_reason():
    assert propose(wrong={}) == [] and propose(cited=[]) == [] and propose(wrong={"FND": 3}) == []
    assert propose(wrong={"CI-04": 0}) == []


def test_what_cannot_be_done_is_not_offered():
    assert [s["kind"] for s in propose(available={})] == ["add_to_tomorrow"]
    assert [s["kind"] for s in propose(tomorrow_taken=True)] == ["practise"]
    assert propose(available={}, tomorrow_taken=True) == []
    assert propose(available={"CI-04": 2})[0]["label_vi"] == "Luyện 2 câu đã duyệt" and propose(available={"CI-04": 2})[0]["n_items"] == 2


def test_the_weakest_cited_topic_is_chosen():
    both = propose(cited=["FND", "CI-04"], wrong={"FND": 3, "CI-04": 2}, available={"FND": 6, "CI-04": 6})
    assert {s["competency_code"] for s in both} == {"FND"} and "sai 3 câu về Khái niệm cơ bản" in both[0]["reason_vi"]
    tie = propose(cited=["FND", "CI-04"], wrong={"FND": 2, "CI-04": 2}, available={"FND": 6, "CI-04": 6})
    assert {s["competency_code"] for s in tie} == {"CI-04"}                 # a tie goes to the first by code
