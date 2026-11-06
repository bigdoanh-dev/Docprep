import unicodedata

import pytest

from yhdp.dictionary import Dictionary, Term, load_dictionary


def d(*terms: Term) -> Dictionary:
    return Dictionary(list(terms))


SXHD = Term(canonical="sốt xuất huyết Dengue", aliases=["SXHD", "SXH Dengue"], type="Bệnh")
THA = Term(canonical="tăng huyết áp", aliases=["THA"], type="Bệnh")
HA = Term(canonical="huyết áp", aliases=["HA"], type="XétNghiệm")


def test_alias_under_two_canonicals_rejected():
    with pytest.raises(ValueError, match="'HA' is used by both"):
        d(HA, Term(canonical="hệ số an toàn", aliases=["HA"], type="Khác"))


def test_duplicate_canonical_rejected():
    with pytest.raises(ValueError, match="used by both"):
        d(THA, Term(canonical="Tăng huyết áp", type="Bệnh"))


def test_normalize_and_expand():
    dic = d(SXHD, THA)
    assert dic.normalize("sxhd") == "sốt xuất huyết Dengue"
    assert dic.normalize("không có") is None
    assert dic.expand("THA") == ["tăng huyết áp", "THA"]
    assert dic.expand("xyz") == ["xyz"]


def test_nfd_input_matches():
    dic = d(SXHD)
    assert dic.normalize(unicodedata.normalize("NFD", "Sốt xuất huyết Dengue")) == SXHD.canonical


def test_find_abbreviations_case_sensitively_and_phrases_by_word():
    dic = d(SXHD, THA, HA)
    assert [t.canonical for t in dic.find("Phân độ THA và SXHD")] == ["tăng huyết áp",
                                                                       "sốt xuất huyết Dengue"]
    assert dic.find("ha ha, tha thứ") == []  # lowercase words are not abbreviations
    found = dic.find("đo huyết áp ở người tăng huyết áp")
    assert [t.canonical for t in found] == ["huyết áp", "tăng huyết áp"]


def test_seed_file_loads_and_has_core_terms():
    dic = load_dictionary()
    assert len(dic.terms) >= 60
    assert dic.normalize("COPD") == "bệnh phổi tắc nghẽn mạn tính"
    assert dic.normalize("OR") == "tỷ suất chênh"
