"""The API's error envelope: `{"error": {"code", "message", "fields"}}`, codes from the contract."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sybille.i18n import t

STATUS: dict[str, int] = {
    "not_authenticated": 401,
    "invalid_credentials": 401,
    "forbidden": 403,
    "not_found": 404,
    "invalid_state": 409,
    "already_bet": 409,
    "insufficient_balance": 409,
    "pseudo_taken": 409,
    "email_taken": 409,
    "invitation_invalid": 409,
    "token_invalid": 409,
    "last_editor": 409,
    "attempts_exhausted": 409,
    "too_large": 413,
    "validation_error": 422,
    "rate_limited": 429,
}


class AppError(Exception):
    def __init__(self, code: str, fields: dict[str, str] | None = None) -> None:
        super().__init__(code)
        if code not in STATUS:
            raise ValueError(f"unknown error code: {code}")
        self.code = code
        self.status = STATUS[code]
        self.fields = fields or {}


def error_response(code: str, status: int, fields: dict[str, str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": t(f"errors.{code}")}
    if fields:
        body["fields"] = fields
    return JSONResponse({"error": body}, status_code=status)


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.code, exc.status, exc.fields)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = [str(part) for part in error["loc"] if part not in ("body", "query", "path")]
        fields[".".join(location) or "body"] = str(error["type"])
    return error_response("validation_error", 422, fields)


_HTTP_CODES = {401: "not_authenticated", 403: "forbidden", 404: "not_found", 405: "not_found"}


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return error_response(_HTTP_CODES.get(exc.status_code, "error"), exc.status_code)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
