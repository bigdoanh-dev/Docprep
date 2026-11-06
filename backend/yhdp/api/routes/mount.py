"""Mount versioned API routes and temporary compatibility aliases."""

from fastapi import APIRouter, FastAPI


def mount_api_router(app: FastAPI, router: APIRouter) -> None:
    app.include_router(router, prefix="/api/v1")
    app.include_router(router, prefix="/api", include_in_schema=False)
