"""Exactly one owner per operation; path prefix alone does not imply ownership."""
from fastapi import APIRouter
from app.api import V1_ROUTERS

CHAT = {"create_chat_session", "list_chat_sessions", "list_chat_messages", "get_passage", "rate_message"}
REPLACED = {"ask_question", "explain_item", "get_hint"}


def partition(service):
    selected = APIRouter()
    for router in V1_ROUTERS:
        for route in router.routes:
            if route.name in REPLACED:
                continue
            if (route.name in CHAT) == (service == "chat"):
                selected.routes.append(route)
    result = [selected]
    if service == "chat":
        from app.api.turns import router
        result.append(router)
    return result


def combined_openapi():
    from app.application import create_app
    import copy
    combined = copy.deepcopy(create_app("mock", service="business").openapi())
    chat = create_app("mock", service="chat").openapi()
    for path, methods in chat["paths"].items():
        target = combined["paths"].setdefault(path, {})
        for method, operation in methods.items():
            if method in target:
                raise RuntimeError(f"Duplicate operation: {method} {path}")
            target[method] = operation
    for name, schema in chat["components"]["schemas"].items():
        existing = combined["components"]["schemas"].get(name)
        if existing and existing != schema:
            raise RuntimeError(f"Conflicting schema {name}")
        combined["components"]["schemas"][name] = schema
    return combined
