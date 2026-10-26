"""The steps of a chat turn (handover/04, "Work trace"): pure. A label is a template over real values."""
from app.chat.retrieval import Passage
from app.chat.trace import check_step, event, glossary_step, item_step, plan, read_step, search_step, stored


def P(doc: str, page: int | None, article: str | None = None) -> Passage:
    return Passage(id=f"{doc}-{page}", document_id=doc, document_title=doc, chapter=None, section=None,
                   page_start=page, article=article, text="", score=1.0)


def test_labels_are_templates_over_real_values():
    assert (search_step(3, None).running_vi, search_step(3, None).done_vi) == ("Đang tìm trong 3 tài liệu", "Đã tìm trong 3 tài liệu")
    scoped = search_step(1, "Sức khỏe quần thể và dự phòng")
    assert (scoped.running_vi, scoped.done_vi) == ("Đang tìm trong học phần Sức khỏe quần thể và dự phòng",
                                                   "Đã tìm trong học phần Sức khỏe quần thể và dự phòng")
    assert glossary_step([]) is None
    terms = glossary_step(["viêm gan B", "lao", "sởi rubella"])
    assert terms.running_vi == terms.done_vi == "Tra thuật ngữ: viêm gan B, lao"
    read = read_step([P("Lịch tiêm chủng mở rộng", 8), P("Lịch tiêm chủng mở rộng", 9), P("Dịch tễ học cơ bản", 58)])
    assert read.running_vi == "Đang đọc 3 đoạn"
    assert read.done_vi == "Đã đọc: Lịch tiêm chủng mở rộng tr. 8, 9; Dịch tễ học cơ bản tr. 58"
    many = read_step([P("A", 1), P("B", 2), P("C", 3), P("D", 4)])
    assert many.done_vi == "Đã đọc: A tr. 1; B tr. 2 và 2 tài liệu khác"
    assert read_step([P("Luật", None, "Điều 3")]).done_vi == "Đã đọc: Luật Điều 3"
    assert read_step([P("A", 8), P("A", 8)]).done_vi == "Đã đọc: A tr. 8"            # a page is named once
    assert item_step().running_vi == item_step().done_vi == "Xem câu hỏi bạn vừa làm"
    assert (check_step().running_vi, check_step(4).done_vi) == ("Đang kiểm tra nhận định với nguồn", "Đã kiểm tra 4 nhận định")


def test_at_most_four_steps_and_the_least_telling_goes_first():
    steps = [search_step(3, None), glossary_step(["lao"]), item_step(), read_step([P("A", 1)]), check_step()]
    assert [s.kind for s in plan(steps, 4)] == ["search", "get_item", "read", "check"]
    assert [s.kind for s in plan(steps, 3)] == ["search", "read", "check"]
    assert [s.id for s in plan([search_step(1, None), None, check_step()], 4)] == ["s1", "s2"]
    assert plan([], 4) == []


def test_an_event_and_the_stored_form():
    step = plan([read_step([P("A", 1)])], 4)[0]
    assert event(step, "running") == {"id": "s1", "kind": "read", "label_vi": "Đang đọc 1 đoạn", "status": "running"}
    assert event(step, "done") == {"id": "s1", "kind": "read", "label_vi": "Đã đọc: A tr. 1", "status": "done"}
    assert stored([step]) == [{"id": "s1", "kind": "read", "label_vi": "Đã đọc: A tr. 1", "status": "done"}]
