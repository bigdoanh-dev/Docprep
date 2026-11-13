"""Shared learner-facing classification and assessment data."""
from typing import Literal

from pydantic import Field

from app.schemas.base import Schema


class QuestionClassification(Schema):
    module_id: str | None = None
    module_name: str | None = None
    core_issue_id: int | None = None
    core_issue_name: str | None = None
    difficulty_label: str | None = None
    bloom_level: Literal[1, 2, 3] | None = None
    bloom_label: str | None = Field(default=None, description="Label of the bank's grouped Bloom band; not a six-level index.")


class AssessmentCount(Schema):
    correct: int
    total: int


class LevelAccuracy(AssessmentCount):
    level: Literal[1, 2, 3, 4, 5, 6]
    label_vi: str


class SpecialtyAccuracy(AssessmentCount):
    module_id: str
    name: str


class BloomSpecialty(Schema):
    module_id: str
    name: str
    levels: list[LevelAccuracy]


class IssueAccuracy(AssessmentCount):
    issue_id: int
    name: str


class SpecialtyIssues(Schema):
    module_id: str
    name: str
    issues: list[IssueAccuracy]


class AssessmentSummary(Schema):
    levels: list[LevelAccuracy] = Field(default_factory=list)
    specialties: list[SpecialtyAccuracy] = Field(default_factory=list)
    bloom_by_specialty: list[BloomSpecialty] = Field(default_factory=list)
    issues_by_specialty: list[SpecialtyIssues] = Field(default_factory=list)
