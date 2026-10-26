from dataclasses import dataclass
from typing import Literal

from app.schemas.common import Role


@dataclass(frozen=True)
class Principal:
    """Who is calling: a learner or a staff member, with the token family of this device."""
    subject_type: Literal["learner", "staff"]
    subject_id: int
    role: Role
    family_id: str
    pseudonym_id: str | None = None   # learners only; the one learner identifier used outside their tables
