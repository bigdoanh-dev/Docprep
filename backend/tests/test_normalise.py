from app.chat.normalise import normalise

GLOSSARY = [{"term": "viêm gan B", "synonyms": ["VGB", "HBV"]}, {"term": "độ nhạy", "synonyms": ["Se", "sensitivity"]}]


def test_abbreviation_expands():
    n = normalise("VGB sơ sinh tiêm khi nào", GLOSSARY)
    assert {"viêm", "gan", "viem", "hbv", "sinh"} <= set(n.terms) and "khi" not in n.terms


def test_text_and_unaccented_forms():
    n = normalise("  Độ Nhạy là gì? ", GLOSSARY)
    assert n.text == "độ nhạy là gì?" and n.unaccented == "do nhay la gi?"
    assert {"se", "sensitivity", "nhạy", "nhay"} <= set(n.terms) and "là" not in n.terms and "la" not in n.terms


def test_synonym_must_be_a_whole_word():
    n = normalise("sẽ tiêm", GLOSSARY)  # "se" inside "sẽ" (unaccented) must not expand độ nhạy
    assert "nhạy" not in n.terms and "sensitivity" not in n.terms


def test_only_stopwords_gives_no_terms():
    assert normalise("là gì?", GLOSSARY).terms == []


def test_concepts_and_loose_tokens_are_separated():
    n = normalise("VGB sơ sinh tiêm khi nào", GLOSSARY)
    assert n.concepts == [["viêm gan b", "vgb", "hbv"]] and n.loose == ["sơ", "sinh", "tiêm"] and not n.plain


def test_plain_query_uses_unaccented_forms():
    n = normalise("do nhay cua test", GLOSSARY)
    assert n.plain and n.concepts == [["do nhay", "se", "sensitivity"]] and n.loose == ["test"]


def test_question_framing_words_are_not_content():
    n = normalise("Phân biệt độ nhạy và viêm gan B như thế nào?", GLOSSARY)
    assert n.loose == [] and len(n.concepts) == 2
    assert normalise("Giải thích độ nhạy chi tiết hơn", GLOSSARY).loose == []
