from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core.response import fail


def _code_for_status(status_code: int) -> str:
    mapping = {
        401: "invalid_refresh",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
    }
    return mapping.get(status_code, "http_error")


def _error_response(status_code: int, code: str, message: str, *, request_id: str | None, details=None, headers=None) -> JSONResponse:
    resp = JSONResponse(
        status_code=status_code,
        content=fail(code=code, message=message, details=details, request_id=request_id),
    )
    if headers:
        resp.headers.update(headers)
    if request_id:
        resp.headers["X-Request-ID"] = request_id
    return resp


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        return _error_response(
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
            request_id=rid,
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        code = _code_for_status(exc.status_code)
        msg = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        details = exc.detail if isinstance(exc.detail, dict) else None
        return _error_response(exc.status_code, code=code, message=msg, details=details, request_id=rid, headers=getattr(exc, "headers", None))

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        code = _code_for_status(exc.status_code)
        msg = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        details = exc.detail if isinstance(exc.detail, dict) else None
        return _error_response(exc.status_code, code=code, message=msg, details=details, request_id=rid, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        return _error_response(
            status_code=500,
            code="internal_error",
            message="Unexpected server error",
            details=None,
            request_id=rid,
        )
