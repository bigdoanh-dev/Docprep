"""Admin: issuing learner accounts in bulk from a CSV file (preview, then confirm)."""
from typing import Literal

from pydantic import Field

from app.schemas.base import Schema, with_example

_ROW = {"display_name": "Nguyễn Thu Hà", "organisation_code": "CSDT-A", "audience": "student"}


class ImportRow(Schema):
    display_name: str
    organisation_code: str
    audience: Literal["student", "graduate"]


class ImportRowError(Schema):
    row: int = Field(description="Line number in the file, the header being line 1.")
    message_vi: str


class ImportPreview(Schema):
    batch_id: int
    rows_total: int
    rows_valid: int
    errors: list[ImportRowError]
    sample: list[ImportRow] = Field(description="The first valid rows, to check the columns were read correctly.")

    model_config = with_example({
        "batch_id": 4, "rows_total": 3, "rows_valid": 2,
        "errors": [{"row": 4, "message_vi": "Mã cơ sở đào tạo “CSDT-Z” không tồn tại."}],
        "sample": [_ROW, {"display_name": "Trần Minh Anh", "organisation_code": "CSDT-B", "audience": "graduate"}],
    })


class IssuedCode(Schema):
    display_name: str
    organisation_code: str
    code: str = Field(description="Shown once; only its hash is stored.")


class ImportResult(Schema):
    batch_id: int
    codes: list[IssuedCode]

    model_config = with_example({
        "batch_id": 4,
        "codes": [{**{k: _ROW[k] for k in ("display_name", "organisation_code")}, "code": "DEMO-0001"},
                  {"display_name": "Trần Minh Anh", "organisation_code": "CSDT-B", "code": "DEMO-0002"}],
    })
