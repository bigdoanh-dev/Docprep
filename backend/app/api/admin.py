"""Admin: bulk account import."""
from fastapi import APIRouter, Request, UploadFile

from app.api.access import access
from app.api.stub import not_implemented
from app.schemas.admin import ImportPreview, ImportResult

router = APIRouter(tags=["admin"])
ADMIN = access("admin")


@router.post("/admin/users/import", response_model=ImportPreview,
             summary="Upload a CSV of learners (display_name, organisation_code, audience); returns a preview",
             **ADMIN)
def import_users(request: Request, file: UploadFile):
    return not_implemented(request, ImportPreview)


@router.post("/admin/users/import/{batch_id}/confirm", response_model=ImportResult,
             summary="Confirm a previewed import; returns the activation codes once", **ADMIN)
def confirm_import(request: Request, batch_id: int):
    return not_implemented(request, ImportResult)
