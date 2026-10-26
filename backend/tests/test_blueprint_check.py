"""The blueprint check: does an exam form hold each group and competency within its range?"""
from app.engine.blueprint import Competency, FormItem, Group, check_form

GROUPS = [
    Group(1, "G1", "G1", 17, 19, list(range(1, 6))), Group(2, "G2", "G2", 16, 20, list(range(6, 17))),
    Group(3, "G3", "G3", 7, 9, [17, 18, 19]), Group(4, "G4", "G4", 17, 21, list(range(20, 28))),
    Group(5, "G5", "G5", 2.5, 3.5, [28, 29]), Group(6, "G6", "G6", 23, 27, list(range(30, 49))),
    Group(7, "G7", "G7", 5, 7, [49, 50, 51]), Group(8, "G8", "G8", 2.5, 3.5, [52, 53, 54]),
]
COMPETENCIES = [
    Competency(1, "C1", 18, 22, [1, 2]), Competency(2, "C2", 37, 43, [3, 4, 5, 6]),
    Competency(3, "C3", 32, 38, [7, 8, 9, 10]), Competency(4, "C4", 4, 6, [11, 12, 13]),
]
FIRST_ISSUE = {g.id: g.issue_ids[0] for g in GROUPS}
FIRST_COMPONENT = {1: 1, 2: 3, 3: 7, 4: 11}


def form(group_counts, competency_counts, bloom=2):
    """A form with the given number of questions per group and per competency (both must sum the same)."""
    issues = [FIRST_ISSUE[g] for g, n in group_counts.items() for _ in range(n)]
    components = [FIRST_COMPONENT[c] for c, n in competency_counts.items() for _ in range(n)]
    assert len(issues) == len(components)
    return [FormItem(f"q{i}", issue, component, bloom) for i, (issue, component) in enumerate(zip(issues, components))]


CONFORMING_GROUPS = {1: 7, 2: 8, 3: 3, 4: 8, 5: 1, 6: 10, 7: 2, 8: 1}
CONFORMING_COMPETENCIES = {1: 8, 2: 16, 3: 14, 4: 2}


def test_the_forty_question_split_conforms():
    report = check_form(form(CONFORMING_GROUPS, CONFORMING_COMPETENCIES), GROUPS, COMPETENCIES)
    assert report.conforms and report.total == 40 and report.problems == []
    assert [s.count for s in report.groups] == [7, 8, 3, 8, 1, 10, 2, 1]
    assert report.groups[4].percent == 2.5 and all(s.within for s in report.groups + report.competencies)


def test_a_ten_question_form_cannot_conform():
    report = check_form(form({1: 2, 2: 2, 3: 1, 4: 2, 6: 3}, {1: 2, 2: 4, 3: 4}), GROUPS, COMPETENCIES)
    assert not report.conforms
    assert any("G5" in p for p in report.problems) and any("C4" in p for p in report.problems)


def test_a_group_over_its_range_is_named():
    counts = {**CONFORMING_GROUPS, 1: 9, 6: 8}
    report = check_form(form(counts, CONFORMING_COMPETENCIES), GROUPS, COMPETENCIES)
    assert [s.id for s in report.groups if not s.within] == [1, 6]
    assert any("G1" in p and "22.5" in p for p in report.problems)


def test_recall_items_are_named():
    items = form(CONFORMING_GROUPS, CONFORMING_COMPETENCIES)
    items[0] = FormItem("q-recall", items[0].core_issue_id, items[0].component_id, 1)
    report = check_form(items, GROUPS, COMPETENCIES)
    assert report.below_band_2 == ["q-recall"] and any("q-recall" in p for p in report.problems)


def test_untagged_items_are_named_and_counted_nowhere():
    items = form(CONFORMING_GROUPS, CONFORMING_COMPETENCIES)
    items[0] = FormItem("q-untagged", None, None, 2)
    report = check_form(items, GROUPS, COMPETENCIES)
    assert report.untagged == ["q-untagged"] and sum(s.count for s in report.groups) == 39
    assert not report.conforms


def test_a_share_exactly_on_its_upper_bound_is_within_range():
    """7 of 100 is 7%, the top of group 7's range; as a float it is 7.000000000000001."""
    groups = {1: 18, 2: 18, 3: 8, 4: 19, 5: 3, 6: 24, 7: 7, 8: 3}
    report = check_form(form(groups, {1: 20, 2: 40, 3: 35, 4: 5}), GROUPS, COMPETENCIES)
    assert report.total == 100 and report.groups[6].within and report.conforms, report.problems


def test_a_share_exactly_on_a_half_percent_bound_is_within_range():
    """7 of 200 is 3.5%, the top of groups 5 and 8."""
    groups = {1: 36, 2: 36, 3: 16, 4: 38, 5: 7, 6: 48, 7: 12, 8: 7}
    report = check_form(form(groups, {1: 40, 2: 80, 3: 70, 4: 10}), GROUPS, COMPETENCIES)
    assert report.total == 200 and report.groups[4].within and report.groups[7].within and report.conforms


def test_an_empty_form_does_not_conform():
    report = check_form([], GROUPS, COMPETENCIES)
    assert report.total == 0 and not report.conforms
