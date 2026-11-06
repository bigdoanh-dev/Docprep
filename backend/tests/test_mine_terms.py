import pytest

from yhdp.dictionary import Dictionary, Term
from yhdp.ingest.mine_terms import (
    Suggestion,
    expansion_for,
    merge,
    mine_abbreviation_list,
    mine_paren_abbreviations,
)
from yhdp.ingest.model import Block, Loc, ParsedDoc


@pytest.mark.parametrize("abbr,before,expected", [
    ("BPTNMT", "Phần 4. Bệnh phổi tắc nghẽn mạn tính", "Bệnh phổi tắc nghẽn mạn tính"),
    ("CPT", "- Chuyển sang truyền cao phân tử", "cao phân tử"),
    ("ĐMMM", "Quy trình xét nghiệm đường máu mao mạch", "đường máu mao mạch"),
    ("Hct", "- Hematocrit", "Hematocrit"),
    ("MAP", "- Huyết áp trung bình", None),  # English abbreviation: left for the LLM
])
def test_expansion_for(abbr, before, expected):
    assert expansion_for(abbr, before) == expected


def doc(*blocks: tuple[str, str]) -> ParsedDoc:
    return ParsedDoc(doc_id="t", blocks=[
        Block(kind="para", text=text, loc=Loc(section_path=[section], anchor=section[:5]))
        for section, text in blocks])


def test_abbreviation_list_pairs_lines():
    d = doc(("DANH MỤC CHỮ VIẾT TẮT", "ALT\nAlanine aminotransferase\nBN\nBệnh nhân"),
            ("DANH MỤC CHỮ VIẾT TẮT", "DNT\nDịch não tủy"))
    assert [(s.alias, s.canonical) for s in mine_abbreviation_list(d)] == [
        ("ALT", "Alanine aminotransferase"), ("BN", "Bệnh nhân"), ("DNT", "Dịch não tủy")]


def test_paren_abbreviations_split_resolved_and_unresolved():
    d = doc(("1. A", "Bệnh không lây nhiễm (BKLN) và huyết áp trung bình (MAP)."))
    resolved, unresolved = mine_paren_abbreviations(d)
    assert [(s.alias, s.canonical) for s in resolved] == [("BKLN", "Bệnh không lây nhiễm")]
    assert [s.alias for s in unresolved] == ["MAP"]


def test_merge_drops_known_pairs_and_flags_conflicts():
    dic = Dictionary([Term(canonical="Haemophilus influenzae", aliases=["HI"], type="TácNhân"),
                      Term(canonical="dịch não tủy", aliases=["DNT"], type="XétNghiệm")])
    s = [Suggestion(canonical="Dịch não tủy", alias="DNT", method="abbr_list", sources=["a"]),
         Suggestion(canonical="Kết quả quá cao", alias="HI", method="initials", sources=["b"]),
         Suggestion(canonical="Ký sinh trùng", alias="KST", method="abbr_list", sources=["c"]),
         Suggestion(canonical="Ký sinh trùng", alias="KST", method="abbr_list", sources=["d"])]
    out = merge(s, dic)
    assert [(x.alias, x.known_as) for x in out] == [("HI", "Haemophilus influenzae"), ("KST", None)]
    assert out[1].sources == ["c", "d"]
