"""Load the blueprint transcription, check it, and write it with the provisional competency tree."""
from pathlib import Path

import yaml

from app.engine.blueprint import FOUNDATION_CODE, Group, group_code, issue_code, midpoint, topic_weights

BLUEPRINT_PATH = Path(__file__).with_name("blueprint.yaml")
N_ISSUES, N_GROUPS, N_COMPETENCIES, N_COMPONENTS = 54, 8, 4, 13


def module_id(group_id: int) -> str:
    """Học phần are the blueprint groups: g1–g8."""
    return f"g{group_id}"


def load_blueprint(path: Path = BLUEPRINT_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def groups_of(data: dict) -> list[Group]:
    return [Group(g["id"], g["name"], g["short_name"], g["weight_min"], g["weight_max"],
                  [i["id"] for i in g["issues"]]) for g in data["groups"]]


def component_ids(data: dict) -> dict[int, list[int]]:
    """Component ids per competency: 1, 2, … in file order."""
    out, next_id = {}, 1
    for c in data["competencies"]:
        out[c["id"]] = list(range(next_id, next_id + len(c["components"])))
        next_id += len(c["components"])
    return out


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _weighted(entry: dict, where: str, required: tuple[str, ...]) -> list[str]:
    errors = [f"{where}: missing {key}" for key in required if entry.get(key) in (None, "")]
    low, high = entry.get("weight_min"), entry.get("weight_max")
    for key, value in (("weight_min", low), ("weight_max", high)):
        if value is not None and not _is_number(value):
            errors.append(f"{where}: {key} must be a number, got {value!r}")
    if _is_number(low) and _is_number(high) and low > high:
        errors.append(f"{where}: weight_min is above weight_max")
    return errors


def _duplicates(ids: list, kind: str) -> list[str]:
    return [f"duplicate {kind} {i}" for i in sorted({i for i in ids if i is not None and ids.count(i) > 1})]


def validate_blueprint(data: dict) -> list[str]:
    errors: list[str] = []
    groups = data.get("groups") or []
    competencies = data.get("competencies") or []
    if len(groups) != N_GROUPS:
        errors.append(f"expected {N_GROUPS} groups, found {len(groups)}")
    if len(competencies) != N_COMPETENCIES:
        errors.append(f"expected {N_COMPETENCIES} competencies, found {len(competencies)}")

    issue_ids: list[int] = []
    for g in groups:
        where = f"group {g.get('id')}"
        errors += _weighted(g, where, ("id", "name", "short_name", "weight_min", "weight_max"))
        issues = g.get("issues") or []
        if not issues:
            errors.append(f"{where}: has no issues")
        errors += [f"{where}: an issue is missing its id or name" for i in issues if not i.get("id") or not i.get("name")]
        issue_ids += [i["id"] for i in issues if i.get("id")]
    errors += _duplicates([g.get("id") for g in groups], "group")
    errors += _duplicates(issue_ids, "issue")
    if sorted(set(issue_ids)) != list(range(1, N_ISSUES + 1)):
        errors.append(f"expected {N_ISSUES} issues numbered 1 to {N_ISSUES}, found {len(set(issue_ids))}")

    n_components = 0
    for c in competencies:
        where = f"competency {c.get('id')}"
        errors += _weighted(c, where, ("id", "name", "weight_min", "weight_max"))
        if not c.get("components"):
            errors.append(f"{where}: has no components")
        n_components += len(c.get("components") or [])
    errors += _duplicates([c.get("id") for c in competencies], "competency")
    # Components are numbered by position, so a missing one would silently renumber every later tag.
    if n_components != N_COMPONENTS:
        errors.append(f"expected {N_COMPONENTS} components, found {n_components}")

    foundation = data.get("foundation") or {}
    if foundation.get("code") != FOUNDATION_CODE or not foundation.get("name"):
        errors.append(f"foundation: needs code {FOUNDATION_CODE} and a name")
    return errors


def write_blueprint(conn, data: dict, foundation_weight: float) -> None:
    """Upsert the blueprint and the provisional tree: G1–G8, then CI-01–CI-54, plus FND."""
    errors = validate_blueprint(data)
    if errors:
        raise ValueError("invalid blueprint:\n" + "\n".join(errors))

    groups = groups_of(data)
    weights = topic_weights(groups, foundation_weight)
    node = """insert into competency_node(code, parent_code, level, name, blueprint_weight, core_issue_id)
              values (%s, %s, %s, %s, %s, %s)
              on conflict (code) do update set parent_code = excluded.parent_code, level = excluded.level,
                name = excluded.name, blueprint_weight = excluded.blueprint_weight,
                core_issue_id = excluded.core_issue_id"""

    for ord_, g in enumerate(data["groups"]):
        conn.execute(
            """insert into core_issue_group(id, name, short_name, weight_min, weight_max) values (%s, %s, %s, %s, %s)
               on conflict (id) do update set name = excluded.name, short_name = excluded.short_name,
                 weight_min = excluded.weight_min, weight_max = excluded.weight_max""",
            (g["id"], g["name"], g["short_name"], g["weight_min"], g["weight_max"]))
        # The học phần of the group. On a re-run its topics and "Sắp có" flag are left to the content loader.
        conn.execute(
            """insert into module(id, name, short_name, ord, core_issue_group_id, competency_codes, coming_soon)
               values (%s, %s, %s, %s, %s, %s, true)
               on conflict (id) do update set name = excluded.name, short_name = excluded.short_name,
                 ord = excluded.ord, core_issue_group_id = excluded.core_issue_group_id""",
            (module_id(g["id"]), g["name"], g["short_name"], ord_, g["id"], [issue_code(i["id"]) for i in g["issues"]]))
        conn.execute(node, (group_code(g["id"]), None, 1, g["name"], midpoint(g["weight_min"], g["weight_max"]), None))
        for i in g["issues"]:
            conn.execute(
                """insert into core_issue(id, group_id, name) values (%s, %s, %s)
                   on conflict (id) do update set group_id = excluded.group_id, name = excluded.name""",
                (i["id"], g["id"], i["name"]))
            code = issue_code(i["id"])
            conn.execute(node, (code, group_code(g["id"]), 2, i["name"], weights[code], i["id"]))

    ids = component_ids(data)
    for c in data["competencies"]:
        conn.execute(
            """insert into exam_competency(id, name, weight_min, weight_max) values (%s, %s, %s, %s)
               on conflict (id) do update set name = excluded.name, weight_min = excluded.weight_min,
                 weight_max = excluded.weight_max""",
            (c["id"], c["name"], c["weight_min"], c["weight_max"]))
        for component_id, name in zip(ids[c["id"]], c["components"]):
            conn.execute(
                """insert into exam_competency_component(id, competency_id, name) values (%s, %s, %s)
                   on conflict (id) do update set competency_id = excluded.competency_id, name = excluded.name""",
                (component_id, c["id"], name))

    conn.execute(node, (FOUNDATION_CODE, None, 1, data["foundation"]["name"], foundation_weight, None))
