import unicodedata

import pytest

from yhdp.blueprint import load_blueprint
from yhdp.settings import settings
from yhdp.sources import load_sources


@pytest.fixture(scope="module")
def sources():
    return load_sources()


def test_registry_ids(sources):
    assert set(sources) == {"qd2760", "qd5904", "qd5642", "ngodoc", "dtch"}


def test_each_source_resolves_to_one_real_file(sources):
    if not any(settings.sources_dir.glob("*.docx")):
        pytest.skip("source documents are provisioned separately")
    paths = [s.resolve() for s in sources.values()]
    assert len(set(paths)) == len(paths)
    assert all(p.exists() for p in paths)


def test_priors_reference_blueprint(sources):
    bp = load_blueprint()
    sub_ids = {s.id for s in bp.mien_subs()}
    for s in sources.values():
        for v in s.van_de_prior:
            bp.van_de_by_id(v)
        assert set(s.mien_prior) <= sub_ids


@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_resolve_ignores_normalization_and_prefix(sources, tmp_path, form):
    name = unicodedata.normalize(form, "1. HƯỚNG DẪN CHẨN ĐOÁN, ĐIỀU TRỊ SỐT XUẤT HUYẾT DENGUE.docx")
    (tmp_path / name).write_bytes(b"")
    (tmp_path / "Dịch tễ học cơ bản.docx").write_bytes(b"")
    assert sources["qd2760"].resolve(tmp_path).name == name


def test_resolve_rejects_ambiguous(sources, tmp_path):
    (tmp_path / "Xử trí ngộ độc.docx").write_bytes(b"")
    (tmp_path / "Xử trí ngộ độc (bản 2).docx").write_bytes(b"")
    with pytest.raises(LookupError):
        sources["ngodoc"].resolve(tmp_path)
