"""The work trace of a chat turn (handover/04-agentic-core.md, "Chat UX contract"). Pure.

A step stands for a stage of the pipeline that ran in this turn. Its label is a template filled with
real values (how many documents, which pages), never text from a model. A step is shown twice, as
running and as done, and the done form is what the message keeps.
"""
from dataclasses import dataclass, replace

# Dropped first when a turn has more steps than may be shown: they say least about the answer.
_DROP_ORDER = ("lookup_glossary", "get_item")


@dataclass(frozen=True)
class Step:
    id: str
    kind: str          # search | read | lookup_glossary | get_item | check
    running_vi: str
    done_vi: str


def search_step(n_documents: int, module_name: str | None) -> Step:
    where = f"học phần {module_name}" if module_name else f"{n_documents} tài liệu"
    return Step("", "search", f"Đang tìm trong {where}", f"Đã tìm trong {where}")


def glossary_step(terms: list[str]) -> Step | None:
    """The glossary terms the question was expanded with; None when it named none."""
    if not terms:
        return None
    label = "Tra thuật ngữ: " + ", ".join(terms[:2])
    return Step("", "lookup_glossary", label, label)


def read_step(passages: list) -> Step:
    """Which pages of which documents were read, in the order retrieval ranked them."""
    places: dict[str, list[str]] = {}
    for p in passages:
        place = f"tr. {p.page_start}" if p.page_start else (p.article or "")
        seen = places.setdefault(p.document_title, [])
        if place and place not in seen:
            seen.append(place)

    def one(title: str, where: list[str]) -> str:
        pages = [w[4:] for w in where if w.startswith("tr. ")]
        others = [w for w in where if not w.startswith("tr. ")]
        parts = ([f"tr. {', '.join(pages)}"] if pages else []) + others
        return f"{title} {', '.join(parts)}".strip()

    shown = [one(title, where) for title, where in list(places.items())[:2]]
    more = len(places) - len(shown)
    done = "Đã đọc: " + "; ".join(shown) + (f" và {more} tài liệu khác" if more > 0 else "")
    return Step("", "read", f"Đang đọc {len(passages)} đoạn", done)


def item_step() -> Step:
    label = "Xem câu hỏi bạn vừa làm"
    return Step("", "get_item", label, label)


def check_step(n_claims: int | None = None) -> Step:
    """The post-check. The number of claims is known only once the model has answered."""
    done = f"Đã kiểm tra {n_claims} nhận định" if n_claims is not None else "Đã kiểm tra nhận định"
    return Step("", "check", "Đang kiểm tra nhận định với nguồn", done)


def plan(steps: list[Step | None], limit: int) -> list[Step]:
    """The steps a turn may show: in order, at most `limit`, numbered s1, s2, …"""
    kept = [s for s in steps if s is not None]
    for kind in _DROP_ORDER:
        if len(kept) > limit:
            kept = [s for s in kept if s.kind != kind]
    return [replace(s, id=f"s{n}") for n, s in enumerate(kept[:limit], start=1)]


def event(step: Step, status: str) -> dict:
    return {"id": step.id, "kind": step.kind, "label_vi": step.running_vi if status == "running" else step.done_vi,
            "status": status}


def stored(steps: list[Step]) -> list[dict]:
    """What the message keeps: every step in its done form."""
    return [event(s, "done") for s in steps]
