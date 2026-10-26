"""The content files in the blueprint format, their validation, and what the seed writes."""
from pathlib import Path

import pytest

from seed import run_seed
from seed.blueprint import load_blueprint
from seed.content import CONTENT_DIR, load_content, unaccent, validate_content

FIX = Path(__file__).parent / "fixtures" / "content"
BLUEPRINT = load_blueprint()
DEMO_COMMENT = "Dữ liệu demo – chưa thẩm định"


def count(conn, sql):
    return conn.execute(f"select count(*) c from {sql}").fetchone()["c"]


def seed_content():
    return load_content(CONTENT_DIR)


def test_unaccent_vietnamese():
    assert unaccent("Viêm gan B sơ sinh, đường") == "viem gan b so sinh, duong"


@pytest.mark.parametrize("directory", [FIX, CONTENT_DIR], ids=["fixture", "seed"])
def test_content_is_valid(directory):
    assert validate_content(load_content(directory), BLUEPRINT) == []


def test_seed_content_keeps_its_size_and_labels():
    c = seed_content()
    passages = [p for d in c["documents"] for p in d["passages"]]
    assert len(passages) >= 30 and len(c["questions"]) == 42 and len(c["glossary"]) >= 20
    assert all(d["demo_label"] == "Tài liệu demo – chưa thẩm định" for d in c["documents"])
    assert {q["competency_code"] for q in c["questions"]} == {"FND", "CI-01", "CI-04"}
    assert {f["kind"] for f in c["exam_forms"]} == {"demo_short", "diagnostic", "assembled"}


def test_script_facts_present():
    text = {p["id"]: p["text"] for d in seed_content()["documents"] for p in d["passages"]}
    assert "24 giờ" in text["tc-p02"] and "viêm gan B" in text["tc-p02"]
    assert "2,5%" in text["dt-p01"]


def test_unit_1_sequence_and_mock():
    c = seed_content()
    u1 = c["modules"][0]["units"][0]
    assert [i["id"] for i in u1["items"]] == ["u1-c1", "u1-q1", "u1-r1", "u1-c2", "u1-q2", "u1-c3", "u1-q3"]
    form = c["exam_forms"][0]
    assert form["id"] == "de-thi-thu-1" and len(form["questions"]) == 10
    unit_qs = {i.get("question") for m in c["modules"] for u in m.get("units", []) for i in u["items"]}
    assert not unit_qs & set(form["questions"])


def test_every_question_has_four_options_a_to_d():
    for q in seed_content()["questions"]:
        assert [o["key"] for o in q["options"]] == ["a", "b", "c", "d"], q["id"]


def test_worked_examples_are_labelled_as_hypothetical():
    for d in seed_content()["documents"]:
        for p in d["passages"]:
            if "Ví dụ" in p["text"] and d["id"] == "DT-DEMO":
                assert "số liệu giả định" in p["text"], p["id"]


def test_law_passages_hold_statute_text_only():
    law = next(d for d in seed_content()["documents"] if d["id"] == "LUAT-PCBTN-2007")
    assert law["validity_note"]
    p4 = next(p for p in law["passages"] if p["id"] == "lt-p04")
    assert "Vì vậy" not in p4["text"]


def test_every_topic_has_enough_questions_to_assemble_from():
    from collections import Counter
    per_topic = Counter(q["competency_code"] for q in seed_content()["questions"])
    assert set(per_topic) == {"FND", "CI-01", "CI-04"}
    assert min(per_topic.values()) >= 5, per_topic


def test_assembled_form_is_defined():
    forms = seed_content()["exam_forms"]
    form = next(f for f in forms if f["id"] == "de-tu-rap")
    assert form["kind"] == "assembled" and form["n_questions"] == 10 and form["questions"] == []
    assert forms[0]["id"] == "de-thi-thu-1"  # the fixed form stays first


def test_the_fixture_content_seeds_and_is_repeatable(conn):
    run_seed(conn, FIX)
    run_seed(conn, FIX)
    assert count(conn, "question where status = 'approved'") == 2
    passages = conn.execute("select page_start, article from passage order by id").fetchall()
    assert all(r["page_start"] or r["article"] for r in passages)
    assert conn.execute("select pseudonym_id from learner").fetchone()["pseudonym_id"] == "HV-DEMO-001"


def test_an_approved_item_changed_in_the_files_is_refused_not_overwritten(conn, tmp_path):
    run_seed(conn, FIX)
    for f in FIX.iterdir():
        (tmp_path / f.name).write_text(
            f.read_text(encoding="utf-8").replace("Câu hỏi thử 1?", "Câu hỏi thử 1, đã sửa?"), encoding="utf-8")
    with pytest.raises(ValueError, match="fx-q-01.*new version"):
        run_seed(conn, tmp_path)
    conn.rollback()
    assert conn.execute("select stem from question where id = 'fx-q-01'").fetchone()["stem"] == "Câu hỏi thử 1?"


def test_seeded_items_went_through_every_status(conn):
    run_seed(conn, FIX)
    steps = [r["to_status"] for r in conn.execute(
        "select to_status from status_transition where target_id = 'fx-q-01' order by id")]
    assert steps == ["draft", "prescreen", "in_review_r1", "in_review_r2", "approved"]
    topics = {r["competency_code"] for r in conn.execute("select competency_code from content_item")}
    assert topics == {"FND"}


@pytest.mark.parametrize("mutate,needle", [
    (lambda c: c["questions"][0]["options"][1].update(correct=True), "exactly one correct"),
    (lambda c: c["questions"][0].update(sources=["nope"]), "unknown passage"),
    (lambda c: c["questions"][0].update(competency_code="CI-99"), "unknown competency"),
    (lambda c: c["questions"][0].update(exam_competency_component=14), "unknown component"),
    (lambda c: c["questions"][0].update(bloom_level=4), "bloom_level"),
    (lambda c: c["exam_forms"][0]["questions"].append("q-missing"), "unknown question"),
    (lambda c: c["modules"][0].update(module="g9"), "unknown module"),
    (lambda c: c["modules"][0]["units"][0]["items"][2].update(after="u-missing"), "remediation"),
    (lambda c: c["documents"][0]["passages"][0].pop("page"), "page or article"),
])
def test_validate_names_the_problem(mutate, needle):
    content = load_content(FIX)
    mutate(content)
    assert any(needle in e for e in validate_content(content, BLUEPRINT))


def test_a_mock_form_must_pass_the_blueprint_check():
    content = load_content(FIX)
    content["exam_forms"][0]["kind"] = "mock"
    errors = validate_content(content, BLUEPRINT)
    assert any(e.startswith("exam form fx-form:") for e in errors)


def test_assembled_form_needs_a_size_the_bank_can_fill():
    content = load_content(FIX)
    content["exam_forms"].append({"id": "fx-auto", "title": "Tự ráp", "kind": "assembled", "n_questions": 2,
                                  "seconds_per_question": 60, "max_attempts": None, "questions": []})
    assert validate_content(content, BLUEPRINT) == []
    content["exam_forms"][-1]["n_questions"] = 3   # the fixture bank has two questions
    assert any("n_questions" in e for e in validate_content(content, BLUEPRINT))
    del content["exam_forms"][-1]["n_questions"]
    assert any("n_questions" in e for e in validate_content(content, BLUEPRINT))


def test_seed_loads_blueprint_content_and_dev_data(conn):
    run_seed(conn)
    assert count(conn, "core_issue") == 54 and count(conn, "passage") >= 30
    assert count(conn, "question where status = 'approved'") == 42 == count(conn, "question")
    assert count(conn, "module") == 8 and count(conn, "module where not coming_soon") == 1
    g1 = conn.execute("select * from module where id = 'g1'").fetchone()
    assert g1["short_name"] == "Sức khỏe quần thể và dự phòng" and "FND" in g1["competency_codes"]
    assert g1["core_issue_group_id"] == 1 and "CI-05" in g1["competency_codes"]
    learner = conn.execute(
        "select l.*, i.display_name from learner l join learner_identity i on i.learner_id = l.id").fetchone()
    assert learner["focus_module_ids"] == ["g1"] and learner["display_name"]


def test_assembled_form_is_seeded_with_its_size(conn):
    run_seed(conn)
    row = conn.execute("select kind, n_questions, question_ids from exam_form where id = 'de-tu-rap'").fetchone()
    assert row == {"kind": "assembled", "n_questions": 10, "question_ids": []}


def test_every_approval_is_backed_by_two_demo_decisions(conn):
    run_seed(conn)
    approved = count(conn, "question where status = 'approved'") + count(conn, "content_item where status = 'approved'")
    assert count(conn, "review_decision") == approved * 2
    assert count(conn, f"review_decision where comment <> '{DEMO_COMMENT}' or decision <> 'pass'") == 0
    reviewers = conn.execute("select count(distinct reviewer_id) c from review_decision").fetchone()["c"]
    assert reviewers == 2 and count(conn, "staff_user where is_demo and password_hash = '!'") == 2
    assert count(conn, "status_transition where to_status = 'approved'") == approved


def test_core_issue_comes_from_the_competency_node(conn):
    run_seed(conn)
    rows = conn.execute("select competency_code, core_issue_id from question").fetchall()
    assert {(r["competency_code"], r["core_issue_id"]) for r in rows} == {("FND", None), ("CI-01", 1), ("CI-04", 4)}


def test_seeding_twice_changes_nothing(conn):
    run_seed(conn)
    tables = ("question", "content_item", "passage", "review_decision", "status_transition", "staff_user", "learner",
              "module", "unit_item", "competency_node", "glossary_term", "exam_form")
    before = {t: count(conn, t) for t in tables}
    run_seed(conn)
    assert {t: count(conn, t) for t in tables} == before


def test_seeding_refuses_in_production(conn, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="dev and test"):
        run_seed(conn)
    assert count(conn, "question") == 0 and count(conn, "learner") == 0


def test_invalid_content_writes_nothing(conn, tmp_path):
    for f in FIX.iterdir():
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8").replace("fx-p01]", "nope]"), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown passage"):
        run_seed(conn, tmp_path)
    assert count(conn, "question") == 0


def test_an_unknown_app_env_is_refused(monkeypatch):
    from app.config import app_env
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(RuntimeError, match="APP_ENV"):
        app_env()
