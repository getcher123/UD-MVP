from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "route",
            "timing_ms",
            "method",
            "status_code",
            "path",
            "client_ip",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _coerce_level(level: str | int | None) -> int:
    if isinstance(level, int):
        return level
    if not level:
        return logging.INFO
    level_name = str(level).upper()
    return getattr(logging, level_name, logging.INFO)


def setup_logging(level: str | int = "INFO") -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())

    root.setLevel(_coerce_level(level))
    root.addHandler(handler)

