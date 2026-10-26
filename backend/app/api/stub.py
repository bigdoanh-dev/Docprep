from typing import TypeVar

from fastapi import Request
from pydantic import BaseModel

from app.errors import ApiError
from app.schemas.base import example

T = TypeVar("T", bound=BaseModel)


def not_implemented_error() -> ApiError:
    return ApiError(501, "not_implemented", "Chức năng này chưa sẵn sàng.")


def mock_example(request: Request, model: type[T]) -> T | None:
    """First line of an implemented route: the model's example in mock mode, None when the route
    should do its real work."""
    return example(model) if request.app.state.mode == "mock" else None


def not_implemented(request: Request, model: type[T]) -> T:
    """Body of a contract stub: the model's example in mock mode, 501 otherwise."""
    if request.app.state.mode == "mock":
        return example(model)
    raise not_implemented_error()
