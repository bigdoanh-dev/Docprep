"""Luyện tập: the học phần list with its filters, and one học phần."""
from app.engine.blueprint import issue_code
from app.errors import ApiError
from app.repo import content
from app.text import unaccent

_CARD_FIELDS = ("id", "name", "short_name", "core_issue_group", "coming_soon", "units_total", "units_done",
                "topics_total")


def _status(m: dict) -> str:
    if m["units_total"] and m["units_done"] == m["units_total"]:
        return "done"
    return "in_progress" if m["units_done"] or m["units_open"] else "not_started"


def list_modules(conn, learner_id: int, *, q: str | None = None, status: str | None = None,
                 group: int | None = None, core_issue: int | None = None, level: int | None = None) -> dict:
    """All eight học phần in blueprint order, narrowed by every filter given."""
    needle = unaccent(q.strip()) if q and q.strip() else None

    def keep(m: dict) -> bool:
        return ((needle is None or needle in unaccent(m["name"]) or needle in unaccent(m["short_name"]))
                and (status is None or _status(m) == status)
                and (group is None or m["core_issue_group"] == group)
                and (core_issue is None or issue_code(core_issue) in m["competency_codes"])
                and (level is None or level in m["bloom_levels"]))

    return {"items": [{k: m[k] for k in _CARD_FIELDS} for m in content.modules(conn, learner_id) if keep(m)]}


def get_module(conn, learner_id: int, module_id: str) -> dict:
    module = content.module(conn, module_id)
    if module is None:
        raise ApiError(404, "module_not_found", "Không tìm thấy học phần.")
    return {**module, "units": content.units_of(conn, learner_id, module_id)}
