"""Base classes for contract models. The models under app/schemas are the API contract (openapi.yaml)."""
from typing import TypeVar

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """A response model. Open, so a later phase can add a field without breaking clients, and every
    field the server sends is marked required in the contract, defaults included."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class RequestSchema(Schema):
    """A request body. Closed: an unknown field is a 422, so a client typo never passes silently."""
    model_config = ConfigDict(extra="forbid")


T = TypeVar("T", bound=BaseModel)


def with_example(value: dict) -> ConfigDict:
    """model_config for a contract model that carries one example (merged with the base class's config)."""
    return ConfigDict(json_schema_extra={"examples": [value]})


def example(model: type[T]) -> T:
    """The model's example, validated. Mock mode serves it and the contract tests check it."""
    extra = model.model_config.get("json_schema_extra")
    examples = extra.get("examples") if isinstance(extra, dict) else None
    if not examples:
        raise LookupError(f"{model.__name__} has no example.")
    return model.model_validate(examples[0])
