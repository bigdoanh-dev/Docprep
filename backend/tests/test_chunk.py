from yhdp.ingest.chunk import TAIL_MIN, TARGET_MAX, chunk_doc, split_table
from yhdp.ingest.model import Block, Loc, ParsedDoc
from yhdp.ingest.parse_docx import FRONT_MATTER
from yhdp.sources import Source

SRC = Source(doc_id="t", file_match="t", title="T", issuer=None, year=None, kind="primary",
             format="docx", citation="section", skip_sections=["^LỜI GIỚI THIỆU"])


def words(text: str) -> int:
    return len(text.split())


def para(path: list[str], n_words: int, word: str = "w", kind: str = "para", **kw) -> Block:
    anchor = "/".join(p.split(".")[0] for p in path) or "root"
    return Block(kind=kind, text=" ".join([word] * n_words), loc=Loc(section_path=path,
                                                                     anchor=anchor), **kw)


def chunk(blocks):
    return chunk_doc(ParsedDoc(doc_id="t", blocks=blocks), SRC, count=words)


def test_never_crosses_sections():
    a, b = ["1. A"], ["2. B"]
    chunks = chunk([para(a, 50), para(b, 50)])
    assert [c.loc.section_path for c in chunks] == [a, b]


def test_greedy_packing_and_tail_merge():
    s = ["1. A"]
    # 400 + 400 > 700 → split; the 30-word tail folds into the second chunk
    chunks = chunk([para(s, 400), para(s, 400), para(s, 30)])
    assert [c.tokens for c in chunks] == [400, 430]
    assert all(c.tokens <= TARGET_MAX or c.tokens < TARGET_MAX + TAIL_MIN for c in chunks)


def test_standalone_blocks_and_ids():
    s = ["1. A"]
    chunks = chunk([para(s, 20), para(s, 5, kind="table"), para(s, 20),
                    para(s, 3, kind="figure", figure_path="figures/x.png", caption="1. A")])
    assert [c.kind for c in chunks] == ["text", "table", "text", "figure"]
    assert [c.chunk_id for c in chunks] == ["t#1#c01", "t#1#c02", "t#1#c03", "t#1#c04"]
    assert chunks[3].figure_path == "figures/x.png"


def test_flattened_table_is_a_table_chunk_flagged_for_review():
    (c,) = chunk([para(["1. A"], 10, needs_review=["table_flattened"])])
    assert c.kind == "table" and c.needs_review == ["table_flattened"]


def test_skips_front_matter_and_skip_sections():
    chunks = chunk([para([FRONT_MATTER], 10), para(["LỜI GIỚI THIỆU"], 10), para(["1. A"], 10)])
    assert [c.loc.section_path for c in chunks] == [["1. A"]]


def test_ids_stable_and_hash_changes_only_for_edited_chunk():
    s, t = ["1. A"], ["2. B"]
    before = chunk([para(s, 10), para(t, 10)])
    after = chunk([para(s, 10), para(t, 10, word="x")])
    assert [c.chunk_id for c in before] == [c.chunk_id for c in after]
    assert before[0].content_hash == after[0].content_hash
    assert before[1].content_hash != after[1].content_hash


def test_split_table_repeats_header():
    rows = [f"| r{i} | " + "x " * 10 + "|" for i in range(30)]
    text = "\n".join(["| a | b |", "| --- | --- |", *rows])
    parts = split_table(text, words, max_tokens=100)
    assert len(parts) > 1
    assert all(p.startswith("| a | b |\n| --- | --- |\n") for p in parts)
    assert sum(len(p.splitlines()) - 2 for p in parts) == 30


def test_cross_reference_only_section_is_dropped():
    s = ["4.4. Sốt do nhiễm vi rút Dengue"]
    xref = Block(kind="para", text="(Xem kế hoạch chăm sóc bệnh nhi Sốt xuất huyết Dengue)",
                 loc=Loc(section_path=s, anchor="4"))
    assert chunk([xref]) == []
    assert len(chunk([xref, para(s, 20)])) == 1  # with real content it stays (merged)
