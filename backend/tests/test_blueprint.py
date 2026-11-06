import pytest

from yhdp.blueprint import load_blueprint


@pytest.fixture(scope="module")
def bp():
    return load_blueprint()


def test_van_de_ids_contiguous(bp):
    assert [v.id for v in bp.van_de] == list(range(1, 55))


def test_de_muc_counts_match_stated(bp):
    counts = {d.id: 0 for d in bp.de_muc}
    for v in bp.van_de:
        counts[v.de_muc] += 1
    assert counts == {d.id: d.n_van_de for d in bp.de_muc}
    assert [d.n_van_de for d in bp.de_muc] == [5, 11, 3, 8, 2, 19, 3, 3]


def test_weight_ranges_feasible(bp):
    for group in (bp.de_muc, bp.mien):
        lo = sum(x.weight[0] for x in group)
        hi = sum(x.weight[1] for x in group)
        assert lo <= 100 <= hi
    assert sum(d.weight[0] for d in bp.de_muc) == 90
    assert sum(m.weight[0] for m in bp.mien) == 91


def test_mien_sub_contents(bp):
    ids = [s.id for s in bp.mien_subs()]
    assert ids == ["1.1", "1.2", "2.1", "2.2", "2.3", "2.4",
                   "3.1", "3.2", "3.3", "3.4", "4.1", "4.2", "4.3"]


def test_names_match_qd51_wording(bp):
    # Names with commas once got truncated by YAML flow mappings.
    assert bp.de_muc[1].name == "Vấn đề sức khỏe cần cấp cứu, sơ cấp cứu ở cấp ban đầu"
    assert bp.de_muc[3].name == "Vấn đề bệnh lý truyền nhiễm cần chẩn đoán, xử trí ở cấp ban đầu"
    assert bp.van_de_by_id(51).name == "Nghiện/rối loạn sử dụng chất (ma túy, thuốc lá, rượu bia)"


def test_every_van_de_has_description(bp):
    assert all(len(v.description) > 40 for v in bp.van_de)


def test_lookups(bp):
    assert bp.van_de_by_id(21).name == "Sốt"
    assert bp.van_de_by_id(21).de_muc == 4
    with pytest.raises(KeyError):
        bp.van_de_by_id(55)


def test_exam_format(bp):
    assert bp.exam.questions == 280
    assert bp.exam.sessions * bp.exam.minutes_per_session == 280
    assert bp.exam.options_per_question == 4
