"""Pre-gate (FR-LRN-05): decline patient-specific clinical advice in code, before any model call."""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config import BACKEND_DIR
from app.text import unaccent

PREGATE_PATH = BACKEND_DIR / "config" / "pregate.yaml"


@dataclass(frozen=True)
class PregateRules:
    version: str
    subject: list[re.Pattern]
    request: list[re.Pattern]


def _compile(patterns: list[str]) -> list[re.Pattern]:
    # Each pattern is kept as written and without diacritics, so "con toi ... uong thuoc gi" is caught too.
    out = []
    for p in patterns:
        out.append(re.compile(p, re.IGNORECASE))
        out.append(re.compile(unaccent(p), re.IGNORECASE))
    return out


def load_patterns(path: Path) -> PregateRules:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return PregateRules(version=raw["version"], subject=_compile(raw["subject"]), request=_compile(raw["request"]))


def is_patient_specific(query: str, rules: PregateRules) -> bool:
    text = " ".join(unicodedata.normalize("NFC", query).lower().split())  # repeated spaces must not defeat a pattern
    forms = (text, unaccent(text))
    has_subject = any(p.search(f) for p in rules.subject for f in forms)
    has_request = any(p.search(f) for p in rules.request for f in forms)
    return has_subject and has_request
