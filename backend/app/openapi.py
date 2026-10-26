"""The API contract, built from the app. openapi.yaml at the repo root is this output, committed."""
import copy

import yaml
from fastapi import FastAPI
from pydantic.json_schema import models_json_schema

from app.config import ROOT_DIR
from app.schemas.base import Schema
from app.schemas.chat import AnswerEvent, FinalEvent, StatusEvent, StepEvent

OPENAPI_PATH = ROOT_DIR / "openapi.yaml"
_REF = "#/components/schemas/{model}"

# Models sent as server-sent events. No route returns them as JSON, so they are added to the
# contract's components here.
SSE_EVENT_MODELS: list[type[Schema]] = [StatusEvent, StepEvent, AnswerEvent, FinalEvent]

API_DESCRIPTION = """\
R1.0 API of the YHDP exam-preparation platform. This file is generated from the backend; do not edit it by hand.

**Conventions**

- Every error response has the body `{"error": {"code", "message_vi", "details"}}`. The codes are listed on \
`ErrorDetail.code`.
- Send the access token as `Authorization: Bearer <token>`. Each operation lists the roles it accepts in `x-roles`.
- Until a learner has recorded the current service consent, every learner operation except those under \
`/v1/auth`, `/v1/consent` and `/v1/me` answers 403 `consent_required`.
- Responses may gain fields and enum values in later versions: clients must ignore unknown fields and treat an \
unknown enum value as a generic case. Request bodies are strict: an unknown field is a 422.
- A collection is returned as an object with `items`; a paginated one adds `next_cursor` (null on the last page), \
to be sent back as `cursor`.
- Operations that take `Idempotency-Key` return the stored response when the same key is sent again.
- UI text in responses is Vietnamese. Timestamps are UTC, ISO 8601.
- An operation that is not implemented yet answers 501 `not_implemented`.
"""


def sse_responses(description: str) -> dict:
    """The 200 response of a streaming route: text/event-stream carrying one of the event models."""
    refs = [{"$ref": _REF.format(model=m.__name__)} for m in SSE_EVENT_MODELS]
    return {200: {"description": description, "content": {"text/event-stream": {"schema": {"oneOf": refs}}}}}


def extend_openapi(spec: dict) -> dict:
    """Add what FastAPI does not derive from the routes: the bearer scheme and the SSE event models."""
    components = spec.setdefault("components", {})
    components.setdefault("securitySchemes", {})["bearer"] = {"type": "http", "scheme": "bearer"}
    _, defs = models_json_schema([(m, "serialization") for m in SSE_EVENT_MODELS], ref_template=_REF)
    components.setdefault("schemas", {}).update(defs.get("$defs", {}))
    return spec


def build_openapi(app: FastAPI) -> dict:
    """The contract of an app made by create_app, which serves this same document at /openapi.json."""
    return copy.deepcopy(app.openapi())


def dump_openapi(spec: dict) -> str:
    return yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120)
