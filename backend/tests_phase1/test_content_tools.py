"""Pure source-port checks: no filesystem corpus, tokenizer download or model server."""
import unicodedata
import pytest
from app.content_tools.dictionary import Dictionary, Term
from app.content_tools.model import ParsedDoc, Block, Loc
from app.content_tools.chunk import chunk_doc, split_table, Source


def test_dictionary_preserves_medical_abbreviation_boundaries_and_conflicts():
    term = Term(canonical='huyết áp', aliases=['HA'], type='Khác')
    dictionary = Dictionary([term])
    assert dictionary.find('ha hôm nay') == []
    assert dictionary.find('THANH') == []
    assert dictionary.find(unicodedata.normalize('NFD', 'Đo HA và huyết áp')) == [term]
    assert dictionary.normalize('ha') == 'huyết áp'
    with pytest.raises(ValueError, match='conflicts'):
        Dictionary([term, Term(canonical='khác', aliases=['HA'], type='Khác')])


def test_chunker_keeps_section_source_review_flags_and_stable_ids():
    def block(text, anchor='A', kind='para', flags=None):
        return Block(text=text, kind=kind, needs_review=flags or [],
                     loc=Loc(section_path=[anchor], anchor=anchor, printed_pages=['12']))
    doc = ParsedDoc(doc_id='source-v1', blocks=[block('nội dung một'),
        block('bảng', kind='table', flags=['table_rebuilt']), block('nội dung hai', 'B'),
        block('bỏ qua', 'SKIP')])
    chunks = chunk_doc(doc, Source('Nguồn', ('^SKIP$',)), count=lambda s: len(s.split()))
    assert [c.chunk_id for c in chunks] == ['source-v1#A#c01', 'source-v1#A#c02', 'source-v1#B#c01']
    assert chunks[1].needs_review == ['table_rebuilt']
    assert all(c.loc.printed_pages == ['12'] and c.schema_version == 'yhdp.chunk.v1' for c in chunks)
    assert chunks == chunk_doc(doc, Source('Nguồn', ('^SKIP$',)), count=lambda s: len(s.split()))
    changed = doc.model_copy(deep=True)
    changed.blocks[0].text = 'nội dung đã đổi'
    assert chunk_doc(changed, Source('Nguồn'), count=len)[0].content_hash != chunks[0].content_hash


def test_oversized_table_repeats_header_for_each_row_group():
    text = '| A | B |\n|--|--|\n|1|2|\n|3|4|\n|5|6|'
    parts = split_table(text, len, max_tokens=27)
    assert len(parts) > 1
    assert all(p.startswith('| A | B |\n|--|--|\n') for p in parts)
    assert sum(p.count('|1|2|') for p in parts) == 1
