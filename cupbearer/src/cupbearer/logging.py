from __future__ import annotations

import contextvars
import logging
import sys
import uuid
from collections.abc import Callable

from fastapi import Request

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
event_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("event_id", default="-")


def _short_id(val: str) -> str:
    """Return first 8 chars of a UUID, or '-' if unset."""
    return val[:8] if val and val != "-" else "-"


def _short_name(name: str) -> str:
    """Return last component of a dotted logger name."""
    return name.rsplit(".", 1)[-1] if "." in name else name


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        record.event_id = event_id_ctx.get("-")
        record.eid = _short_id(record.event_id)  # type: ignore[attr-defined]
        record.rid = _short_id(record.request_id)  # type: ignore[attr-defined]
        record.short_name = _short_name(record.name)  # type: ignore[attr-defined]
        return True


def configure_logging(level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(short_name)s [%(eid)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Silence noisy third-party loggers.
    for noisy in ("httpx", "httpcore", "mem0", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def correlation_id_middleware(request: Request, call_next: Callable):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    event_id = request.headers.get("X-Event-ID", "-")

    req_token = request_id_ctx.set(request_id)
    evt_token = event_id_ctx.set(event_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_ctx.reset(req_token)
        event_id_ctx.reset(evt_token)
