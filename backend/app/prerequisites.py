"""The prerequisite map (config/prerequisites.yaml) as SQL that fills competency_node.prerequisite_codes.

Machine-made and unreviewed (experiments/prerequisites/propose.py, 2026-11-23). Only an empty value is
filled, so a reviewer's own list is never overwritten. Used by migration 0021 and by the blueprint
seed (which recreates the tree on a fresh database)."""
import re
from pathlib import Path

import yaml

PATH = Path(__file__).resolve().parents[1] / "config" / "prerequisites.yaml"
CODE = re.compile(r"[A-Z]+(-\d+)?")


def load() -> dict[str, list[str]]:
    data = yaml.safe_load(PATH.read_text(encoding="utf-8")) or {}
    for code, pres in data.items():
        if not all(CODE.fullmatch(c) for c in [code, *pres]):
            raise ValueError(f"bad competency code in {PATH.name}: {code} {pres}")
    return data


def statements() -> list[str]:
    return [f"update competency_node set prerequisite_codes = '{{{','.join(pres)}}}' "
            f"where code = '{code}' and prerequisite_codes = '{{}}'" for code, pres in load().items()]
