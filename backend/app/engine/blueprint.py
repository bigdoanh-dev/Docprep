"""The exam blueprint as rules: topic weights and the check of an exam form. Pure, no database."""
from dataclasses import dataclass
from fractions import Fraction

FOUNDATION_CODE = "FND"


@dataclass(frozen=True)
class Group:
    """A group of core issues, with the share of the exam it must hold (percent)."""
    id: int
    name: str
    short_name: str
    weight_min: float
    weight_max: float
    issue_ids: list[int]


def issue_code(issue_id: int) -> str:
    return f"CI-{issue_id:02d}"


def group_code(group_id: int) -> str:
    return f"G{group_id}"


def midpoint(weight_min: float, weight_max: float) -> float:
    return (float(weight_min) + float(weight_max)) / 2


def topic_weights(groups: list[Group], foundation_weight: float) -> dict[str, float]:
    """Weight of each topic for priority. The blueprint weighs groups, as ranges; a core issue gets
    its group's midpoint shared equally among the group's issues (open issue 26)."""
    weights = {issue_code(i): midpoint(g.weight_min, g.weight_max) / len(g.issue_ids)
               for g in groups for i in g.issue_ids}
    weights[FOUNDATION_CODE] = foundation_weight
    return weights


@dataclass(frozen=True)
class Competency:
    """An exam competency, with the share of the exam it must hold (percent)."""
    id: int
    name: str
    weight_min: float
    weight_max: float
    component_ids: list[int]


@dataclass(frozen=True)
class FormItem:
    """A question of an exam form, as the blueprint sees it."""
    question_id: str
    core_issue_id: int | None
    component_id: int | None
    bloom_level: int


@dataclass(frozen=True)
class Share:
    """How much of a form one group or competency holds, against its range."""
    id: int
    name: str
    count: int
    percent: float
    weight_min: float
    weight_max: float
    within: bool


@dataclass(frozen=True)
class FormReport:
    total: int
    groups: list[Share]
    competencies: list[Share]
    untagged: list[str]        # questions with no core issue or no competency component
    below_band_2: list[str]    # recall items; the blueprint weighs only Vận dụng and above
    problems: list[str]

    @property
    def conforms(self) -> bool:
        return not self.problems


def _share(entry, count: int, total: int) -> Share:
    percent = count / total * 100 if total else 0.0
    # Compared exactly: as floats, 7 of 100 is 7.000000000000001 and would miss a 7% upper bound.
    low, high = Fraction(str(entry.weight_min)), Fraction(str(entry.weight_max))
    within = total > 0 and low * total <= count * 100 <= high * total
    return Share(entry.id, entry.name, count, percent, float(entry.weight_min), float(entry.weight_max), within)


def _out_of_range(kind: str, share: Share) -> str:
    return (f"{kind} {share.name}: {share.count} of the form's questions = {share.percent:g}%, "
            f"outside {share.weight_min:g}–{share.weight_max:g}%")


def check_form(items: list[FormItem], groups: list[Group], competencies: list[Competency]) -> FormReport:
    """Compare a form with the blueprint: each group's and each competency's share of the questions
    against its range, every question tagged on both axes, and no recall item."""
    total = len(items)
    group_of = {i: g.id for g in groups for i in g.issue_ids}
    competency_of = {c: comp.id for comp in competencies for c in comp.component_ids}
    untagged = [it.question_id for it in items if it.core_issue_id is None or it.component_id is None]
    tagged = [it for it in items if it.core_issue_id is not None and it.component_id is not None]

    group_counts = {g.id: 0 for g in groups}
    competency_counts = {c.id: 0 for c in competencies}
    for it in tagged:
        if it.core_issue_id in group_of:
            group_counts[group_of[it.core_issue_id]] += 1
        if it.component_id in competency_of:
            competency_counts[competency_of[it.component_id]] += 1

    group_shares = [_share(g, group_counts[g.id], total) for g in groups]
    competency_shares = [_share(c, competency_counts[c.id], total) for c in competencies]
    below_band_2 = [it.question_id for it in items if it.bloom_level < 2]

    problems = []
    if total == 0:
        problems.append("the form has no questions")
    problems += [_out_of_range("group", s) for s in group_shares if not s.within]
    problems += [_out_of_range("competency", s) for s in competency_shares if not s.within]
    if untagged:
        problems.append("no core issue or competency component: " + ", ".join(untagged))
    if below_band_2:
        problems.append("recall items (Bloom band 1) are not part of the exam: " + ", ".join(below_band_2))
    return FormReport(total, group_shares, competency_shares, untagged, below_band_2, problems)
