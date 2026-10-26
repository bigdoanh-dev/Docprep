"""The /v1 API: one router per domain. Each route is a contract stub until its phase implements it."""
from fastapi import APIRouter

from app.api import (account, admin, auth, cards, chat, dashboard, exams, home, modules, practice, progress, reports,
                     review, session, units)

V1_ROUTERS: list[APIRouter] = [
    auth.router, account.router, home.router, session.router, practice.router, modules.router, units.router,
    chat.router, reports.router, exams.router, cards.router, progress.router, review.router, admin.router,
    dashboard.router,
]
