"""Luyện tập: the học phần list and one học phần."""
from typing import Literal

from fastapi import APIRouter, Query, Request

from app.api.access import Caller, access
from app.api.deps import Conn
from app.api.stub import mock_example
from app.schemas.modules import ModuleDetail, ModuleList
from app.services import modules as modules_service

router = APIRouter(tags=["modules"])
LEARNER = access("learner")


@router.get("/modules", response_model=ModuleList, summary="Học phần with progress, filtered", **LEARNER)
def list_modules(request: Request, q: str | None = None,
                 status: Literal["not_started", "in_progress", "done"] | None = None,
                 group: int | None = None, core_issue: int | None = None,
                 level: int | None = Query(None, ge=1, le=3, description="Bloom band."),
                 conn=Conn, principal=Caller):
    return mock_example(request, ModuleList) or modules_service.list_modules(
        conn, principal.subject_id, q=q, status=status, group=group, core_issue=core_issue, level=level)


@router.get("/modules/{module_id}", response_model=ModuleDetail, summary="Units of a học phần", **LEARNER)
def get_module(request: Request, module_id: str, conn=Conn, principal=Caller):
    return mock_example(request, ModuleDetail) or modules_service.get_module(conn, principal.subject_id, module_id)
