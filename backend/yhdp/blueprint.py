"""QĐ 51/QĐ-HĐYKQG exam blueprint: miền, đề mục and the 54 vấn đề."""

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from yhdp.settings import settings


class BaseModel(BaseModel):
    # Unknown keys usually mean a YAML typo (e.g. an unquoted comma in a flow mapping).
    model_config = ConfigDict(extra="forbid")


class MienSub(BaseModel):
    id: str
    name: str


class Mien(BaseModel):
    id: int
    name: str
    weight: tuple[float, float]
    sub: list[MienSub]


class DeMuc(BaseModel):
    id: int
    name: str
    n_van_de: int
    weight: tuple[float, float]


class VanDe(BaseModel):
    id: int
    de_muc: int
    name: str
    description: str
    approved: bool = False


class Exam(BaseModel):
    questions: int
    sessions: int
    minutes_per_session: int
    options_per_question: int
    bloom_levels: list[str]


class Blueprint(BaseModel):
    source: str
    exam: Exam
    mien: list[Mien]
    de_muc: list[DeMuc]
    van_de: list[VanDe]

    @model_validator(mode="after")
    def _check_refs(self):
        de_muc_ids = {d.id for d in self.de_muc}
        for v in self.van_de:
            if v.de_muc not in de_muc_ids:
                raise ValueError(f"vấn đề {v.id} references unknown đề mục {v.de_muc}")
        return self

    def mien_subs(self) -> list[MienSub]:
        return [s for m in self.mien for s in m.sub]

    def van_de_by_id(self, van_de_id: int) -> VanDe:
        for v in self.van_de:
            if v.id == van_de_id:
                return v
        raise KeyError(van_de_id)


@cache
def load_blueprint(path: Path | None = None) -> Blueprint:
    path = path or settings.blueprint_path
    return Blueprint.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
