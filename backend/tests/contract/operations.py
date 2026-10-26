"""What the contract must contain. Each domain adds its operations here before it is written."""
from fastapi import FastAPI
from fastapi.routing import RouteContext, iter_route_contexts

# Every (METHOD, path) the contract must contain.
EXPECTED: set[tuple[str, str]] = {
    # auth, consent, account
    ("POST", "/v1/auth/activate"),
    ("POST", "/v1/auth/staff/login"),
    ("POST", "/v1/auth/refresh"),
    ("POST", "/v1/auth/logout"),
    ("GET", "/v1/consent/current"),
    ("POST", "/v1/consent"),
    ("DELETE", "/v1/consent"),
    ("GET", "/v1/me"),
    ("PATCH", "/v1/me"),
    ("GET", "/v1/me/data"),
    ("DELETE", "/v1/me"),
    # chat
    ("POST", "/v1/chat/sessions"),
    ("GET", "/v1/chat/sessions"),
    ("GET", "/v1/chat/sessions/{session_id}/messages"),
    ("POST", "/v1/chat/sessions/{session_id}/messages"),
    ("POST", "/v1/chat/suggestions/{suggestion_id}/accept"),
    ("GET", "/v1/passages/{passage_id}"),
    ("POST", "/v1/messages/{message_id}/rating"),
    # học phần, units, tutor
    ("GET", "/v1/modules"),
    ("GET", "/v1/modules/{module_id}"),
    ("GET", "/v1/units/{unit_id}/next"),
    ("POST", "/v1/units/{unit_id}/responses"),
    ("POST", "/v1/units/{unit_id}/advance"),
    ("POST", "/v1/items/{question_id}/explain"),
    ("POST", "/v1/items/{question_id}/hint"),
    # practice sets, daily session, Home
    ("GET", "/v1/home"),
    ("GET", "/v1/session/today"),
    ("GET", "/v1/session/today/practice"),
    ("POST", "/v1/session/today/practice/responses"),
    ("POST", "/v1/session/today/practice/complete"),
    ("GET", "/v1/practice-sets/{set_id}"),
    ("POST", "/v1/practice-sets/{set_id}/responses"),
    ("POST", "/v1/practice-sets/{set_id}/complete"),
    # exams
    ("GET", "/v1/exams"),
    ("POST", "/v1/exams/{form_id}/attempts"),
    ("GET", "/v1/attempts/{attempt_id}"),
    ("PUT", "/v1/attempts/{attempt_id}/answers/{question_id}"),
    ("POST", "/v1/attempts/{attempt_id}/submit"),
    ("GET", "/v1/attempts/{attempt_id}/results"),
    ("GET", "/v1/attempts/{attempt_id}/items/{question_id}"),
    # cards, decks, progress
    ("GET", "/v1/cards/due"),
    ("POST", "/v1/cards/{card_id}/reviews"),
    ("PATCH", "/v1/cards/{card_id}"),
    ("GET", "/v1/decks"),
    ("GET", "/v1/progress/skills"),
    ("GET", "/v1/progress/rhythm"),
    # reports, review workbench, admin
    ("POST", "/v1/reports"),
    ("GET", "/v1/review/queue"),
    ("GET", "/v1/review/items/{item_id}"),
    ("POST", "/v1/review/items/{item_id}/decisions"),
    ("GET", "/v1/review/reports"),
    ("POST", "/v1/admin/users/import"),
    ("POST", "/v1/admin/users/import/{batch_id}/confirm"),
    # ministry dashboard (phase 6)
    ("GET", "/v1/admin/dashboard/overview"),
    ("GET", "/v1/admin/dashboard/export"),
}

# Operations that are real. The others answer 501 in real mode.
IMPLEMENTED: set[tuple[str, str]] = {
    ("POST", "/v1/auth/activate"),
    ("POST", "/v1/auth/staff/login"),
    ("POST", "/v1/auth/refresh"),
    ("POST", "/v1/auth/logout"),
    ("GET", "/v1/consent/current"),
    ("POST", "/v1/consent"),
    ("DELETE", "/v1/consent"),
    ("GET", "/v1/me"),
    ("PATCH", "/v1/me"),
    ("GET", "/v1/me/data"),
    ("DELETE", "/v1/me"),
    # phase 4: the learner flows of the kickoff demo
    ("GET", "/v1/modules"),
    ("GET", "/v1/modules/{module_id}"),
    ("GET", "/v1/units/{unit_id}/next"),
    ("POST", "/v1/units/{unit_id}/responses"),
    ("POST", "/v1/units/{unit_id}/advance"),
    ("GET", "/v1/exams"),
    ("POST", "/v1/exams/{form_id}/attempts"),
    ("GET", "/v1/attempts/{attempt_id}"),
    ("PUT", "/v1/attempts/{attempt_id}/answers/{question_id}"),
    ("POST", "/v1/attempts/{attempt_id}/submit"),
    ("GET", "/v1/attempts/{attempt_id}/results"),
    ("GET", "/v1/attempts/{attempt_id}/items/{question_id}"),
    ("GET", "/v1/cards/due"),
    ("POST", "/v1/cards/{card_id}/reviews"),
    ("POST", "/v1/items/{question_id}/explain"),
    ("POST", "/v1/chat/sessions"),
    ("GET", "/v1/chat/sessions"),
    ("GET", "/v1/chat/sessions/{session_id}/messages"),
    ("POST", "/v1/chat/sessions/{session_id}/messages"),
    ("GET", "/v1/passages/{passage_id}"),
    ("GET", "/v1/home"),
    # phase 5A: practice sets and the daily session
    ("GET", "/v1/practice-sets/{set_id}"),
    ("POST", "/v1/practice-sets/{set_id}/responses"),
    ("POST", "/v1/practice-sets/{set_id}/complete"),
    ("GET", "/v1/session/today"),
    ("GET", "/v1/session/today/practice"),
    ("POST", "/v1/session/today/practice/responses"),
    ("POST", "/v1/session/today/practice/complete"),
    # phase 5B: progress, decks, suspending a card, the hint
    ("GET", "/v1/progress/skills"),
    ("GET", "/v1/progress/rhythm"),
    ("GET", "/v1/decks"),
    ("PATCH", "/v1/cards/{card_id}"),
    ("POST", "/v1/items/{question_id}/hint"),
    # phase 7A: the chat contract additions
    ("POST", "/v1/chat/suggestions/{suggestion_id}/accept"),
    ("POST", "/v1/messages/{message_id}/rating"),
    # phase 6B: the ministry dashboard
    ("GET", "/v1/admin/dashboard/overview"),
    ("GET", "/v1/admin/dashboard/export"),
}

# Operations that stream server-sent events.
SSE: set[tuple[str, str]] = {
    ("POST", "/v1/chat/sessions/{session_id}/messages"),
    ("POST", "/v1/items/{question_id}/explain"),
}

# Operations that answer with a file, and its media type.
BINARY: dict[tuple[str, str], str] = {
    ("GET", "/v1/admin/dashboard/export"): "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Multipart payloads for operations that take a file.
FILES: dict[tuple[str, str], dict] = {
    ("POST", "/v1/admin/users/import"): {
        "file": ("users.csv",
                 "display_name,organisation_code,audience\nNguyễn Thu Hà,CSDT-A,student\n".encode("utf-8"),
                 "text/csv"),
    },
}


def v1_operations(app: FastAPI) -> list[tuple[str, str, RouteContext]]:
    """Method, full path and route of every /v1 operation.

    FastAPI keeps included routers lazily, so `app.routes` does not list their routes;
    `iter_route_contexts` does, with the prefix applied and the route's attributes proxied.
    """
    return sorted(
        ((method, route.path, route)
         for route in iter_route_contexts(app.routes) if route.path.startswith("/v1")
         for method in route.methods),
        key=lambda op: (op[1], op[0]))
