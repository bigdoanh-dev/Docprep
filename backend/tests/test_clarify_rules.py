"""When a question names a term experts flagged as ambiguous, and what is offered instead. Pure."""
from app.chat import clarify

G = [{"term": "tỷ lệ mắc", "synonyms": [], "ambiguous": True, "sense_group": "g"},
     {"term": "tỷ lệ mới mắc", "synonyms": ["incidence", "mới mắc"], "ambiguous": False, "sense_group": "g"},
     {"term": "tỷ lệ hiện mắc", "synonyms": ["prevalence", "hiện mắc"], "ambiguous": False, "sense_group": "g"},
     {"term": "lao", "synonyms": ["BCG"], "ambiguous": False, "sense_group": None}]


def test_an_ambiguous_term_gives_its_senses_as_ready_questions():
    term, options = clarify.options("Tỷ lệ mắc tính thế nào?", G)
    assert term == "tỷ lệ mắc" and options == [
        {"term": "tỷ lệ hiện mắc", "label_vi": "Tỷ lệ hiện mắc", "query": "Tỷ lệ hiện mắc tính thế nào?"},
        {"term": "tỷ lệ mới mắc", "label_vi": "Tỷ lệ mới mắc", "query": "Tỷ lệ mới mắc tính thế nào?"}]
    inside = clarify.options("Cho biết cách tính tỷ lệ mắc của bệnh lao.", G)[1]
    assert inside[0]["query"] == "Cho biết cách tính tỷ lệ hiện mắc của bệnh lao."


def test_no_question_is_asked_back_when_it_is_not_needed():
    assert clarify.options("Tỷ lệ hiện mắc tính thế nào?", G) is None                      # a sense is named, not the bare term
    assert clarify.options("Tỷ lệ mắc, tức tỷ lệ mới mắc, tính thế nào?", G) is None       # the term and one of its senses
    assert clarify.options("Tỷ lệ mắc (prevalence) là gì?", G) is None                     # a sense named by its synonym
    assert clarify.options("BCG tiêm khi nào?", G) is None
    assert clarify.options("Tỷ lệ mắc là gì?", [G[0], G[1], G[3]]) is None                 # one sense is no choice
    assert clarify.options("Tỷ lệ mắc là gì?", []) is None


def test_typing_without_accents_and_more_than_four_senses():
    term, options = clarify.options("ty le mac tinh the nao", G)
    assert term == "tỷ lệ mắc" and options[0]["query"] == "tỷ lệ hiện mắc tinh the nao"
    assert clarify.options("Tỷ   lệ mắc là gì?", G)[1][0]["query"] == "Tỷ lệ hiện mắc là gì?"   # spacing does not hide the term
    many = [G[0]] + [{"term": f"nghĩa {c}", "synonyms": [], "ambiguous": False, "sense_group": "g"} for c in "edcba"]
    assert [o["term"] for o in clarify.options("tỷ lệ mắc là gì", many)[1]] == ["nghĩa a", "nghĩa b", "nghĩa c", "nghĩa d"]
