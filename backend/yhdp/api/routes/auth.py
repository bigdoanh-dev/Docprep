"""Authentication and client metadata routes."""

import time
from collections import deque
from typing import get_args

from fastapi import APIRouter, FastAPI, HTTPException, Request

from yhdp.api.auth import authenticate, make_token
from yhdp.api.dependencies import DB, User
from yhdp.api.routes.mount import mount_api_router
from yhdp.api.schemas import Login
from yhdp.blueprint import load_blueprint
from yhdp.dictionary import TermType, load_dictionary
from yhdp.ingest.tag import BLOOM, CONTENT_TYPES, MCQ_ELIGIBLE, POPULATIONS

LOGIN_WINDOW_S, LOGIN_MAX_FAILS = 15 * 60, 10


def register_auth_routes(app: FastAPI, secret: str, failures: dict[str, deque]) -> None:
    router = APIRouter()

    @router.post("/auth/login")
    def login(body: Login, request: Request, con: DB):
        client = request.client.host if request.client else "?"
        ip = request.headers.get("cf-connecting-ip") or client
        key, now = f"{ip}:{body.username}", time.monotonic()
        recent = failures[key]
        while recent and now - recent[0] > LOGIN_WINDOW_S:
            recent.popleft()
        if len(recent) >= LOGIN_MAX_FAILS:
            raise HTTPException(429, "too many failed attempts; try again in 15 minutes")
        row = authenticate(con, body.username, body.password)
        if row is None:
            recent.append(now)
            raise HTTPException(401, "wrong username or password")
        recent.clear()
        return {"token": make_token(row["username"], row["role"], secret),
                "username": row["username"], "role": row["role"]}

    @router.get("/me")
    def me(u: User):
        return {"username": u["sub"], "role": u["role"]}

    @router.get("/meta")
    def meta(_: User, con: DB):
        bp = load_blueprint()
        return {
            "de_muc": [d.model_dump() for d in bp.de_muc],
            "van_de": [{"id": v.id, "de_muc": v.de_muc, "name": v.name,
                        "description": v.description} for v in bp.van_de],
            "mien": [{"id": m.id, "name": m.name, "sub": [s.model_dump() for s in m.sub]}
                     for m in bp.mien],
            "bloom": list(BLOOM), "mcq_eligible": sorted(MCQ_ELIGIBLE, key=BLOOM.index),
            "content_types": list(CONTENT_TYPES), "populations": list(POPULATIONS),
            "terms": sorted((t.canonical for t in load_dictionary().terms), key=str.casefold),
            "term_types": list(get_args(TermType)),
            "documents": [dict(r) for r in con.execute(
                "SELECT doc_id, title, issuer, year FROM documents ORDER BY doc_id")],
        }
    mount_api_router(app, router)
