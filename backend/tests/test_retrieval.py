from app.chat.normalise import normalise
from app.chat.retrieval import get_passages, search
from app.config import settings
from tests.conftest import glossary

R = settings()["retrieval"]


def find(conn, q, module_id=None):
    return search(conn, normalise(q, glossary(conn)), R["top_k"], R["min_score"], module_id)


def test_scripted_question_hits_birth_dose(conn, learner):
    hits = find(conn, "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?")
    assert hits[0].id == "tc-p02" and hits[0].document_title == "Lịch tiêm chủng mở rộng" and hits[0].page_start == 8
    assert len(hits) <= R["top_k"] and hits == sorted(hits, key=lambda h: -h.score)


def test_no_diacritics_same_top_hit(conn, learner):  # Review Focus 1
    assert find(conn, "vac xin viem gan b mui so sinh tiem khi nao")[0].id == "tc-p02"


def test_abbreviation_query_hits_via_glossary(conn, learner):
    assert find(conn, "VGB sơ sinh")[0].id == "tc-p02"


def test_epidemiology_and_law_questions_hit_their_passages(conn, learner):
    assert find(conn, "Phân biệt tỷ lệ hiện mắc và tỷ lệ mới mắc")[0].id in ("dt-p01", "dt-p02", "dt-p03")
    assert find(conn, "Bệnh tả thuộc nhóm nào theo Luật phòng chống bệnh truyền nhiễm?")[0].id == "lt-p01"


def test_out_of_corpus_returns_nothing(conn, learner):
    assert find(conn, "Phác đồ hoá trị ung thư phổi giai đoạn III") == []


def test_module_filter_limits_to_module_topics(conn, learner):
    # All stopgap content sits in học phần 1; the other học phần have none yet.
    assert find(conn, "tỷ lệ", module_id="g1")
    assert find(conn, "tỷ lệ", module_id="g2") == []


def test_empty_terms_returns_nothing(conn, learner):
    assert find(conn, "là gì?") == []


def test_get_passages_by_id(conn, learner):
    got = get_passages(conn, ["lt-p01", "dt-p01"])
    assert set(got) == {"lt-p01", "dt-p01"} and got["lt-p01"].article == "Điều 3, khoản 1, điểm a"


def test_concept_written_with_a_dash_in_the_corpus_is_found(conn, learner):  # final review, Important 3
    assert find(conn, "Nghiên cứu bệnh chứng là gì?")[0].id == "dt-p10"
    assert find(conn, "nghien cuu benh chung la gi")[0].id == "dt-p10"
    assert find(conn, "Nghiên cứu bệnh-chứng là gì?")[0].id == "dt-p10"


def test_two_concept_question_brings_both_definition_passages(conn, learner):  # final review, Important 5
    ids = [h.id for h in find(conn, "Phân biệt tỷ lệ hiện mắc và tỷ lệ mới mắc")]
    assert {"dt-p01", "dt-p02", "dt-p03"} <= set(ids)
