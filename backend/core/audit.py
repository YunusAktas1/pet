from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

_logger = logging.getLogger("audit")
_logger.setLevel(logging.INFO)


class Metrics:
    counters: dict[str, int] = {}

    @classmethod
    def incr(cls, key: str) -> None:
        cls.counters[key] = cls.counters.get(key, 0) + 1

    @classmethod
    def snapshot(cls) -> dict[str, int]:
        return dict(cls.counters)


def audit(event: str, **fields: Any) -> None:
    Metrics.incr(event)
    payload = {"event": event, "ts": datetime.now(timezone.utc).isoformat()}
    payload.update({k: v for k, v in fields.items() if v is not None})
    try:
        _logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        # Best-effort logging should not break the app
        _logger.info({"event": event})
