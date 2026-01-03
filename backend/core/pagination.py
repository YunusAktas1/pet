from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status


def parse_limit(limit: Optional[int], *, default: int = 20, max_limit: int = 100) -> int:
    if limit is None:
        return default
    if limit < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="limit must be >= 1")
    if limit > max_limit:
        limit = max_limit
    return limit


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        padding = '=' * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + padding)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        return data
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid cursor",
        ) from err


def parse_cursor_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid cursor",
        ) from err
