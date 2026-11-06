"""Optional local hosting for the learner and reviewer single-page apps."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def register_frontend_routes(app: FastAPI, web_dir: Path, review_dir: Path) -> None:
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404)
        root = web_dir
        source = "web/"
        if path == "review" or path.startswith("review/"):
            root = review_dir
            source = "web-review/"
            path = path.removeprefix("review").lstrip("/")
        resolved_root = root.resolve()
        target = (root / path).resolve()
        if path and target.is_file() and resolved_root in target.parents:
            return FileResponse(target)
        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(503, f"web app not built; run `npm run build` in {source}")
        return FileResponse(index)
