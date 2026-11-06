import json

import httpx
import numpy as np
import pytest

from yhdp.answer import cited
from yhdp.dictionary import Dictionary, Term
from yhdp.ingest.chunk import chunk_doc
from yhdp.ingest.load_db import embed_missing, load_doc
from yhdp.ingest.model import Block, Loc, ParsedDoc
from yhdp.llm import Ollama
from yhdp.retrieve import Retriever, expansions, fts_query, rrf
from yhdp.sources import Source
from yhdp.store.db import connect

SRC = Source(doc_id="t", file_match="t", title="Hướng dẫn T", issuer="QĐ 1/QĐ-BYT", year=2020,
             kind="primary", format="docx", citation="section")


def chunks(*texts: str):
    blocks = [Block(kind="para", text=t, loc=Loc(section_path=[f"{i}. S{i}"], anchor=str(i)))
              for i, t in enumerate(texts, start=1)]
    return chunk_doc(ParsedDoc(doc_id="t", blocks=blocks), SRC, count=lambda s: len(s.split()))


VOCAB = ("sốt", "dengue", "huyết", "áp", "kháng", "sinh")


def fake_embed(request: httpx.Request) -> httpx.Response:
    """Deterministic bag-of-words embedding over a tiny vocabulary."""
    texts = json.loads(request.content)["input"]
    vecs = [[t.lower().count(w) + 0.01 for w in VOCAB] for t in texts]
    return httpx.Response(200, json={"embeddings": vecs})


@pytest.fixture
def con(tmp_path):
    return connect(tmp_path / "t.db")


@pytest.fixture
def llm(tmp_path):
    return Ollama(base_url="http://x", transport=httpx.MockTransport(fake_embed), log_dir=tmp_path)


def test_load_is_idempotent_and_tracks_changes(con):
    first = load_doc(con, SRC, chunks("sốt dengue", "huyết áp"))
    assert (first.added, first.unchanged) == (2, 0)
    again = load_doc(con, SRC, chunks("sốt dengue", "huyết áp"))
    assert (again.added, again.changed, again.unchanged) == (0, 0, 2)
    edited = load_doc(con, SRC, chunks("sốt dengue nặng"))
    assert (edited.changed, edited.removed) == (1, 1)
    assert con.execute("SELECT count(*) FROM chunks_fts").fetchone()[0] == 1


def test_human_tag_survives_reingestion(con):
    load_doc(con, SRC, chunks("sốt dengue"))
    con.execute("INSERT INTO chunk_tags (chunk_id, content_hash, tags, source) "
                "SELECT chunk_id, content_hash, '{}', 'human' FROM chunks")
    load_doc(con, SRC, chunks())  # chunk disappears …
    load_doc(con, SRC, chunks("sốt dengue"))  # … and comes back
    assert con.execute("SELECT count(*) FROM chunk_tags WHERE source = 'human'").fetchone()[0] == 1


def test_embed_only_new_or_changed(con, llm):
    load_doc(con, SRC, chunks("sốt dengue", "huyết áp"))
    assert embed_missing(con, llm) == 2
    assert embed_missing(con, llm) == 0
    load_doc(con, SRC, chunks("sốt dengue", "huyết áp cao"))
    assert embed_missing(con, llm) == 1


def test_hybrid_search_finds_relevant_chunk(con, llm):
    load_doc(con, SRC, chunks("sốt dengue có dấu hiệu cảnh báo", "huyết áp cao", "kháng sinh"))
    embed_missing(con, llm)
    hits = Retriever(con, llm).search("dấu hiệu cảnh báo sốt dengue", k=2)
    assert hits[0].loc.section_path == ["1. S1"]
    assert set(hits[0].ranks) == {"dense", "bm25"}


def test_rrf_rewards_agreement():
    fused = rrf({"dense": ["a", "b", "c"], "bm25": ["b", "d"]})
    assert fused[0][0] == "b"
    assert fused[0][2] == {"dense": 2, "bm25": 1}


def test_fts_query_quotes_words_and_drops_syntax():
    assert fts_query('SXHD "nặng" OR (sốc)?') == '"sxhd" OR "nặng" OR "or" OR "sốc"'
    assert fts_query("?!") == ""


def test_query_expansion_adds_synonym_phrases():
    dic = Dictionary([Term(canonical="sốt xuất huyết Dengue", aliases=["SXHD"], type="Bệnh")])
    extra = expansions("Phân độ SXHD", dic)
    assert extra == ["sốt xuất huyết Dengue"]
    assert fts_query("Phân độ SXHD", extra) == \
        '"phân" OR "độ" OR "sxhd" OR "sốt xuất huyết dengue"'


def test_cited_splits_valid_and_invalid():
    assert cited("A [S1]. B [S3][S1]. C [S9].", 6) == ([1, 3], [9])


def test_vectors_are_float32_normalized(con, llm):
    load_doc(con, SRC, chunks("sốt dengue"))
    embed_missing(con, llm)
    vec = np.frombuffer(con.execute("SELECT vec FROM chunk_vectors").fetchone()[0], np.float32)
    assert np.isclose(np.linalg.norm(vec), 1.0)
