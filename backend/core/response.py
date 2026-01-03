from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[ApiError] = None


def ok(data: Any) -> dict:
    return ApiResponse(success=True, data=data, error=None).model_dump()


def fail(code: str, message: str, details: Optional[dict[str, Any]] = None) -> dict:
    return ApiResponse(
        success=False,
        data=None,
        error=ApiError(code=code, message=message, details=details),
    ).model_dump()
