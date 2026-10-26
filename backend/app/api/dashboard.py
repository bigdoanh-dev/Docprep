"""Quản lý cấp Bộ: the national overview and its export. Read-only, aggregates only."""
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.api.access import Caller, access
from app.api.deps import Conn, Now
from app.api.stub import mock_example
from app.schemas.base import example
from app.schemas.dashboard import AdminOverview, Audience
from app.services import dashboard as dashboard_service
from app.services import dashboard_export

router = APIRouter(tags=["dashboard"])

PERIOD = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-09"],
               description="A calendar month in local time, `YYYY-MM`. Default: the last complete month.")
SCHOOL = Query(None, description="An organisation code. Default: all schools.")
REGION = Query(None, description="Default: every region.")

VIEWERS = access("ministry_viewer", "admin")
EXPORT = access("ministry_viewer", "admin", responses={200: {
    "description": "The view as an .xlsx file: one sheet per block, the same figures as the page.",
    "content": {dashboard_export.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}}}})


@router.get("/admin/dashboard/overview", response_model=AdminOverview,
            summary="Tổng quan toàn quốc: usage, question bank, AI answer safety, by school; small groups withheld",
            **VIEWERS)
def get_overview(request: Request, period: str | None = PERIOD, school: str | None = SCHOOL,
                 audience: Audience | None = None, region: str | None = REGION, conn=Conn, now=Now):
    return mock_example(request, AdminOverview) or dashboard_service.overview(
        conn, {"period": period, "school": school, "audience": audience, "region": region}, now)


@router.get("/admin/dashboard/export", response_class=Response,
            summary="The same view as an Excel file", **EXPORT)
def export_overview(request: Request, format: Literal["xlsx"] = "xlsx", period: str | None = PERIOD,
                    school: str | None = SCHOOL, audience: Audience | None = None, region: str | None = REGION,
                    conn=Conn, now=Now, caller=Caller):
    if request.app.state.mode == "mock":
        view = example(AdminOverview).model_dump(mode="json")
    else:
        filters = {"period": period, "school": school, "audience": audience, "region": region}
        view = AdminOverview.model_validate(
            dashboard_service.export(conn, filters, caller.subject_id, now)).model_dump(mode="json")
    return Response(dashboard_export.build(view), media_type=dashboard_export.MEDIA_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{dashboard_export.file_name(view)}"'})
