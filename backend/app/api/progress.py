"""Tiến độ: Năng lực and Nhịp học."""
from typing import Literal

from fastapi import APIRouter, Request

from app.api.access import Learner, access
from app.api.deps import Conn, Now
from app.api.stub import mock_example
from app.schemas.progress import ProgressRhythm, ProgressSkills
from app.services import progress as progress_service

router = APIRouter(tags=["progress"])
LEARNER = access("learner")


@router.get("/progress/skills", response_model=ProgressSkills,
            summary="Năng lực: coverage, priorities, real mock scores, accuracy by level", **LEARNER)
def get_progress_skills(request: Request, scope: Literal["latest3", "all"] = "latest3", conn=Conn, now=Now,
                        learner=Learner):
    return mock_example(request, ProgressSkills) or progress_service.skills(conn, learner, scope, now)


@router.get("/progress/rhythm", response_model=ProgressRhythm,
            summary="Nhịp học: study time, memory, recall by học phần, due forecast", **LEARNER)
def get_progress_rhythm(request: Request, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, ProgressRhythm) or progress_service.rhythm(conn, learner, now)
