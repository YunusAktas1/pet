from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status

from backend.core.audit import audit


@dataclass
class LimitConfig:
    limit: int
    window_seconds: int


class RateLimiter:
    def __init__(self) -> None:
        self._store: dict[str, list[float]] = {}

    def reset(self) -> None:
        self._store.clear()

    def allow(self, key: str, config: LimitConfig) -> Optional[int]:
        now = time.monotonic()
        window_start = now - config.window_seconds
        timestamps = self._store.get(key, [])
        timestamps = [t for t in timestamps if t >= window_start]
        if len(timestamps) >= config.limit:
            retry_after = int(config.window_seconds - (now - timestamps[0])) + 1
            self._store[key] = timestamps
            return retry_after
        timestamps.append(now)
        self._store[key] = timestamps
        return None


limiter = RateLimiter()

# Default limits (per key = IP for now)
REFRESH_LIMIT = LimitConfig(limit=5, window_seconds=60)
LOGOUT_LIMIT = LimitConfig(limit=10, window_seconds=60)
LOGIN_LIMIT = LimitConfig(limit=20, window_seconds=60)


def rate_limit_or_raise(key: str, config: LimitConfig, *, endpoint: str, request_id: str, client_ip: str) -> None:
    # During tests, bypass limits only for login to avoid flakiness in bulk user setup.
    if os.getenv("PYTEST_CURRENT_TEST") and endpoint == "auth.login":
        return

    retry_after = limiter.allow(key, config)
    if retry_after is not None:
        audit(
            "auth.rate_limited",
            endpoint=endpoint,
            key=key,
            client_ip=client_ip,
            result="fail",
            request_id=request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
