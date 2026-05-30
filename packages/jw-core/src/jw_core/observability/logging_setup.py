"""Structured logging setup.

VISION.md item: "Logging estructurado (mencionado pero no implementado en
Fase 9)".

Two flavours:
  - text (default): human-readable
  - json: one JSON object per line for downstream ingest

Switch with `JW_LOG_FORMAT=json`. Level via `JW_LOG_LEVEL=DEBUG/INFO/...`.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Render a record as one-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Pick up any extra structured fields the caller attached.
        for k, v in record.__dict__.items():
            if k in payload or k.startswith("_") or k in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                continue
            payload[k] = v
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | None = None, *, fmt: str | None = None) -> None:
    """Idempotent: replaces the root handler with a console handler."""
    level_name = (level or os.getenv("JW_LOG_LEVEL", "INFO")).upper()
    chosen_fmt = (fmt or os.getenv("JW_LOG_FORMAT", "text")).lower()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    if chosen_fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root.addHandler(handler)
    root.setLevel(getattr(logging, level_name, logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured event. With json formatter the fields appear as keys."""
    logger.info(event, extra=fields)
