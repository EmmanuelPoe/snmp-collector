"""Shared structured logging + correlation IDs (Step 5.1 / plan Step 35).

Single source of truth, vendored byte-identically into backend/, manager/, and
agent/ so each flat-layout service can import it directly. `scripts/sync_shared.py`
regenerates the copies and `scripts/check_shared.py` (run in CI) fails on drift.

One JSON object per log line, shared across all services:

    ts, level, service, logger, msg, correlation_id[, <extras>]

`<extras>` are any non-reserved keyword passed via ``logger.info(..., extra={...})``
(e.g. agent_id, device_ip, file_id), so one upload can be followed end-to-end.

Correlation IDs travel in the ``X-Correlation-ID`` header. `CorrelationMiddleware`
(a pure-ASGI middleware, so the contextvar it sets is visible to endpoints —
unlike a BaseHTTPMiddleware) reads or mints one per request on the FastAPI
services; the agent stamps a fresh one per poll/upload cycle. `correlation_headers()`
forwards the current id on outbound httpx calls.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

CORRELATION_HEADER = "X-Correlation-ID"

# Minimal ASGI type aliases so CorrelationMiddleware type-checks without a
# Starlette dependency (the agent has no web framework).
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# Per-async-task / per-thread correlation id. Empty until set by inbound
# middleware (backend/manager) or stamped per cycle (agent).
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

# Standard LogRecord attributes; anything else on the record is a caller-supplied
# extra and is emitted as a top-level field.
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(value: str | None) -> str:
    """Adopt `value` as the current correlation id, minting one if blank. Returns it."""
    cid = value or uuid.uuid4().hex
    _correlation_id.set(cid)
    return cid


def new_correlation_id() -> str:
    """Stamp a fresh correlation id and return it (agent poll/upload cycles)."""
    return set_correlation_id(None)


def correlation_headers() -> dict[str, str]:
    """Header dict forwarding the current correlation id on outbound httpx calls."""
    cid = _correlation_id.get()
    return {CORRELATION_HEADER: cid} if cid else {}


class JsonFormatter(logging.Formatter):
    """Render each record as one JSON line in the shared schema."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": _correlation_id.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service: str, level: int = logging.INFO) -> None:
    """Install the JSON formatter as the process-wide root handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service))
    logging.basicConfig(level=level, handlers=[handler], force=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class CorrelationMiddleware:
    """Pure-ASGI middleware: adopt the inbound X-Correlation-ID (or mint one) into
    the contextvar for the life of the request, and echo it on the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        header_name = CORRELATION_HEADER.lower().encode()
        inbound = dict(scope["headers"]).get(header_name)
        cid = set_correlation_id(inbound.decode() if inbound else None)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((header_name, cid.encode()))
            await send(message)

        await self.app(scope, receive, send_with_header)
