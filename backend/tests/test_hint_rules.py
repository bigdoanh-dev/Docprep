"""The hint check: pure. A hint that gives the answer away never reaches the learner."""
import pytest

from app.engine.hint import MAX_LENGTH, pointer, reveals_answer, usable

OPTIONS = [{"key": "a", "text": "2,5%", "is_correct": True}, {"key": "b", "text": "5%", "is_correct": False},
           {"key": "c", "text": "0,25%", "is_correct": False}, {"key": "d", "text": "25%", "is_correct": False}]
WORDS = [{"key": "a", "text": "Tỷ lệ mới mắc", "is_correct": True}, {"key": "b", "text": "Tỷ lệ hiện mắc", "is_correct": False}]


@pytest.mark.parametrize("hint", [
    "Kết quả là 2,5%.",                       # the correct option's text
    "Đáp án là A.", "Đáp án đúng: a", "Hãy chọn phương án b.", "Câu trả lời là D", "Có thể loại (C) trước.",
    "Loại B vì mẫu số sai.", "Xem lại (a).",
])
def test_a_hint_that_names_an_option_or_holds_the_answer_is_caught(hint):
    assert reveals_answer(hint, OPTIONS) is True and usable(hint, OPTIONS) is False


@pytest.mark.parametrize("hint", [
    "Hãy xác định mẫu số trước: đó là toàn bộ dân số của xã tại thời điểm khảo sát.",
    "Chú ý phân biệt số ca đang mắc và số ca mới.",
    "Hãy chọn đúng mẫu số rồi mới chia.",       # "chọn" without naming an option
])
def test_a_hint_that_only_points_the_way_passes(hint):
    assert reveals_answer(hint, OPTIONS) is False and usable(hint, OPTIONS) is True


STEM = "Một xã có 2.000 dân; ngày 1/1 có 50 người đang mắc lao. Tỷ lệ hiện mắc là?"
YES_NO = [{"key": "a", "text": "Có", "is_correct": True}, {"key": "b", "text": "Không", "is_correct": False}]
MEASURES = [{"key": "a", "text": "Tỷ suất chênh (OR).", "is_correct": True},
            {"key": "b", "text": "Nguy cơ tương đối (RR)", "is_correct": False},
            {"key": "c", "text": "Tỷ lệ hiện mắc", "is_correct": False}]
HOURS = [{"key": "a", "text": "24 giờ", "is_correct": True}, {"key": "b", "text": "48 giờ", "is_correct": False},
         {"key": "c", "text": "72 giờ", "is_correct": False}, {"key": "d", "text": "7 ngày", "is_correct": False}]


@pytest.mark.parametrize("hint", [
    "Kết quả là 2.5%.", "Kết quả là 2,5 %.", "Kết quả là 2,50%.", "Khoảng 2,5 phần trăm.",      # the answer, written another way
    "50 ÷ 2.000 = 0,025.", "Lấy 50 chia cho 2.000 rồi nhân 100.",                               # a figure the question does not give
])
def test_a_number_the_question_does_not_give_is_caught(hint):
    assert reveals_answer(hint, OPTIONS, STEM) is True


@pytest.mark.parametrize("hint", [
    "A là đúng.", "Ý A.", "Câu A.", "Đáp án chính xác là A.", "Đáp án đúng nhất là A.", "Đáp án sẽ là A.",
    'Đáp án "A".', "Đáp án **A**.", "Chọn [A]", "A) là hợp lý.", "Phương án đầu tiên.", "The answer is A.",
    "Loại trừ B, C và D.", "B, C, D đều sai.", "Không phải B.",
])
def test_every_way_of_pointing_at_an_option_is_caught(hint):
    assert reveals_answer(hint, OPTIONS, STEM) is True


def test_a_short_or_partly_quoted_answer_is_caught():
    assert reveals_answer("Câu trả lời là có.", YES_NO, "Bệnh này có lây không?") is True
    assert reveals_answer("Nghiên cứu bệnh–chứng dùng tỷ suất chênh.", MEASURES, "Chỉ số nào?") is True
    assert reveals_answer("Hãy nghĩ đến OR.", MEASURES, "Chỉ số nào?") is True
    assert reveals_answer("Kết quả là 5%.", [{"key": "a", "text": "5%", "is_correct": True},
                                             {"key": "b", "text": "10%", "is_correct": False}], "Trong 5 năm có 100 ca.") is True
    # ruling out every other option by its text tells as much as naming the answer
    assert reveals_answer("Không phải nguy cơ tương đối (RR), cũng không phải tỷ lệ hiện mắc.", MEASURES, "Chỉ số nào?") is True


@pytest.mark.parametrize("hint, options, stem", [
    ("Tử số là 50 người đang mắc; hãy tìm mẫu số trong đề bài.", OPTIONS, STEM),            # a figure from the question
    ("Bệnh viêm gan B lây qua đường máu; hãy nhớ mốc tiêm ngay sau sinh.", HOURS, "Viêm gan B: mũi sơ sinh tiêm khi nào?"),
    ("Hãy phân biệt chỉ số của nghiên cứu thuần tập với nghiên cứu bệnh–chứng.", MEASURES, "Chỉ số nào?"),
])
def test_a_hint_that_uses_the_questions_own_words_passes(hint, options, stem):
    assert reveals_answer(hint, options, stem) is False and usable(hint, options, stem) is True


def test_accents_case_and_spacing_do_not_hide_the_answer():
    assert reveals_answer("Đó chính là TỶ  LỆ   MỚI MẮC.", WORDS) is True
    assert reveals_answer("Do chinh la ty le moi mac", WORDS) is True
    assert reveals_answer("Hãy nghĩ về các ca xuất hiện trong kỳ.", WORDS) is False


def test_only_a_short_text_is_usable():
    assert usable("", OPTIONS) is False and usable("   ", OPTIONS) is False and usable(None, OPTIONS) is False
    assert usable({"hint": "x"}, OPTIONS) is False
    assert usable("x" * MAX_LENGTH, OPTIONS) is True and usable("x" * (MAX_LENGTH + 1), OPTIONS) is False


def test_the_pointer_says_where_to_look():
    source = {"document": "Dịch tễ học cơ bản", "chapter": "Chương 2. Đo lường bệnh trạng", "section": "2.1 Tỷ lệ hiện mắc",
              "page": 58, "article": None}
    assert pointer(source) == "Hãy xem lại 2.1 Tỷ lệ hiện mắc trong Dịch tễ học cơ bản, trang 58."
    assert pointer({**source, "section": None}) == "Hãy xem lại Chương 2. Đo lường bệnh trạng trong Dịch tễ học cơ bản, trang 58."
    assert pointer({**source, "page": None, "article": "Điều 3, khoản 1"}) == (
        "Hãy xem lại 2.1 Tỷ lệ hiện mắc trong Dịch tễ học cơ bản, Điều 3, khoản 1.")
    assert pointer({"document": "Dịch tễ học cơ bản", "chapter": None, "section": None, "page": 58, "article": None}) == (
        "Hãy xem lại Dịch tễ học cơ bản.")
