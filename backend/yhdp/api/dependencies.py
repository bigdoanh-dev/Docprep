"""Shared FastAPI dependencies for database access and authenticated requests."""

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from yhdp.api.auth import read_token
from yhdp.store.db import connect


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    con = connect(request.app.state.db_path, check_same_thread=False)
    try:
        yield con
    finally:
        con.close()


def claims_from(token: str | None, secret: str) -> dict:
    claims = read_token(token, secret) if token else None
    if claims is None:
        raise HTTPException(401, "not signed in")
    return claims


def get_user(request: Request,
             authorization: Annotated[str | None, Header()] = None) -> dict:
    token = authorization.removeprefix("Bearer ") if authorization else None
    return claims_from(token, request.app.state.jwt_secret)


def get_reviewer(user: Annotated[dict, Depends(get_user)]) -> dict:
    if user["role"] != "reviewer":
        raise HTTPException(403, "reviewers only")
    return user


DB = Annotated[sqlite3.Connection, Depends(get_db)]
User = Annotated[dict, Depends(get_user)]
Reviewer = Annotated[dict, Depends(get_reviewer)]
