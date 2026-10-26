from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message_vi: str, details: dict | None = None):
        super().__init__(code)
        self.status, self.code, self.message_vi, self.details = status, code, message_vi, details


def error_response(status: int, code: str, message_vi: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message_vi": message_vi, "details": details}}, status_code=status)


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message_vi, exc.details)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"path": ".".join(str(part) for part in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return error_response(422, "invalid_request", "Dữ liệu gửi lên không hợp lệ.", {"fields": fields})


_HTTP_ERRORS = {
    404: ("not_found", "Không tìm thấy đường dẫn."),
    405: ("method_not_allowed", "Phương thức không được hỗ trợ."),
}


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Errors raised by the framework itself (unknown path, wrong method) use the same body as ours."""
    code, message_vi = _HTTP_ERRORS.get(exc.status_code, ("http_error", "Yêu cầu không thực hiện được."))
    return error_response(exc.status_code, code, message_vi)


async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Anything we did not foresee still answers with the error body. The server logs the traceback."""
    return error_response(500, "internal_error", "Có lỗi xảy ra. Vui lòng thử lại.")
