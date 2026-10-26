"""Trang chủ."""
from fastapi import APIRouter, Request

from app.api.access import Learner, access
from app.api.deps import Conn, Now
from app.api.stub import mock_example
from app.schemas.home import HomeView
from app.services import home as home_service

router = APIRouter(tags=["home"])


@router.get("/home", response_model=HomeView, summary="Home: quick review, next mock, tutor suggestions, recent",
            **access("learner"))
def get_home(request: Request, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, HomeView) or home_service.home(conn, learner, now)
