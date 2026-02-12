"""Structured JSON logging setup. Never log full prompts or user content."""

import json
import logging
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "message": record.getMessage(),
            "level": record.levelname,
        }
        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        if getattr(record, "endpoint", None):
            payload["endpoint"] = record.endpoint
        if getattr(record, "status_code", None):
            payload["status_code"] = record.status_code
        if getattr(record, "latency_ms", None):
            payload["latency_ms"] = record.latency_ms
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON formatter."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
