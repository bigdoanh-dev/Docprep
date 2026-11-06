"""Protected source-file routes."""

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse

from yhdp.api.dependencies import claims_from
from yhdp.api.routes.mount import mount_api_router
from yhdp.settings import settings


def register_file_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.get("/files/{doc_id}/figures/{name}")
    def figure(doc_id: str, name: str, request: Request, t: str = Query()):
        claims_from(t, request.app.state.jwt_secret)
        base = (settings.derived_dir / doc_id / "figures").resolve()
        path = (base / name).resolve()
        if path.parent != base or not path.is_file():
            raise HTTPException(404, "no such figure")
        return FileResponse(path)
    mount_api_router(app, router)
