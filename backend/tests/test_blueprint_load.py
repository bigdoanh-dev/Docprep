"""The blueprint transcription, its validation, and what the loader writes."""
import copy

import pytest

from app.engine.blueprint import Group, topic_weights
from seed.blueprint import load_blueprint, validate_blueprint, write_blueprint


def test_transcription_has_the_published_shape():
    data = load_blueprint()
    assert [len(g["issues"]) for g in data["groups"]] == [5, 11, 3, 8, 2, 19, 3, 3]
    assert sorted(i["id"] for g in data["groups"] for i in g["issues"]) == list(range(1, 55))
    assert [len(c["components"]) for c in data["competencies"]] == [2, 4, 4, 3]
    assert [(g["weight_min"], g["weight_max"]) for g in data["groups"]] == [
        (17, 19), (16, 20), (7, 9), (17, 21), (2.5, 3.5), (23, 27), (5, 7), (2.5, 3.5)]
    assert [(c["weight_min"], c["weight_max"]) for c in data["competencies"]] == [(18, 22), (37, 43), (32, 38), (4, 6)]
    assert validate_blueprint(data) == []


def test_midpoints_cover_the_whole_exam():
    data = load_blueprint()
    assert sum((g["weight_min"] + g["weight_max"]) / 2 for g in data["groups"]) == 100
    assert sum((c["weight_min"] + c["weight_max"]) / 2 for c in data["competencies"]) == 100


def test_topic_weight_is_the_group_midpoint_shared_by_its_issues():
    groups = [Group(1, "A", "A", 17, 19, [1, 2, 3, 4, 5]), Group(5, "E", "E", 2.5, 3.5, [28, 29])]
    weights = topic_weights(groups, foundation_weight=2.0)
    assert weights["CI-01"] == pytest.approx(3.6) and weights["CI-28"] == pytest.approx(1.5)
    assert weights["FND"] == 2.0 and len(weights) == 8


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d["groups"][0]["issues"].pop(), "54 issues"),
    (lambda d: d["groups"][0].update(weight_min=20), "weight_min"),
    (lambda d: d["groups"][2].update(issues=[]), "no issues"),
    (lambda d: d["groups"][1]["issues"][0].update(id=1), "duplicate issue 1"),
    (lambda d: d["competencies"][3].update(components=[]), "no components"),
    (lambda d: d["groups"][0].pop("short_name"), "short_name"),
    (lambda d: d["groups"][1].update(id=1), "duplicate group 1"),
    (lambda d: d["competencies"][1].update(id=1), "duplicate competency 1"),
    (lambda d: d["competencies"][0]["components"].pop(), "13 components"),
    (lambda d: d["groups"][0].update(weight_max="19%"), "must be a number"),
])
def test_a_wrong_blueprint_is_named(mutate, needle):
    data = copy.deepcopy(load_blueprint())
    mutate(data)
    assert any(needle in message for message in validate_blueprint(data))


def test_the_blueprint_alone_can_be_loaded_in_production(conn, monkeypatch):
    """It is reference data, not demo content: a production database needs it before any question exists."""
    from seed import run_blueprint
    monkeypatch.setenv("APP_ENV", "production")
    run_blueprint(conn)
    assert conn.execute("select count(*) c from core_issue").fetchone()["c"] == 54
    assert conn.execute("select count(*) c from module").fetchone()["c"] == 8
    assert conn.execute("select count(*) c from question").fetchone()["c"] == 0


def test_a_wrong_blueprint_writes_nothing(conn):
    data = copy.deepcopy(load_blueprint())
    data["groups"][0]["issues"].pop()
    with pytest.raises(ValueError, match="54 issues"):
        write_blueprint(conn, data, 2.0)
    assert conn.execute("select count(*) c from core_issue_group").fetchone()["c"] == 0


def test_write_creates_blueprint_rows_and_the_provisional_tree(conn):
    write_blueprint(conn, load_blueprint(), 2.0)
    write_blueprint(conn, load_blueprint(), 2.0)      # repeatable

    def count(table):
        return conn.execute(f"select count(*) c from {table}").fetchone()["c"]

    assert (count("core_issue_group"), count("core_issue"), count("exam_competency"),
            count("exam_competency_component"), count("competency_node")) == (8, 54, 4, 13, 63)
    # The eight học phần come with the blueprint, so a database with no demo content still has them.
    g4 = conn.execute("select * from module where id = 'g4'").fetchone()
    assert count("module") == 8 and g4["short_name"] == "Bệnh truyền nhiễm" and g4["coming_soon"] is True
    assert g4["competency_codes"] == [f"CI-{i}" for i in range(20, 28)] and g4["core_issue_group_id"] == 4
    node = conn.execute("select * from competency_node where code = 'CI-04'").fetchone()
    assert node["parent_code"] == "G1" and node["level"] == 2 and node["core_issue_id"] == 4
    assert node["blueprint_weight"] == pytest.approx(3.6) and node["provisional"] is True
    fnd = conn.execute("select * from competency_node where code = 'FND'").fetchone()
    assert fnd["core_issue_id"] is None and fnd["blueprint_weight"] == 2.0
    twenty = conn.execute("select group_id from core_issue where id = 20").fetchone()
    assert twenty["group_id"] == 4
