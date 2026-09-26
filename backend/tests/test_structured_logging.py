"""Shared structured logging + correlation IDs (Step 5.1 / plan Step 35)."""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from logging_json import (
    CORRELATION_HEADER,
    JsonFormatter,
    correlation_headers,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)

REPO = Path(__file__).resolve().parent.parent.parent
REQUIRED_FIELDS = {"ts", "level", "service", "logger", "msg", "correlation_id"}


def _format(record_kwargs: dict, service: str = "backend") -> dict:
    record = logging.makeLogRecord({"name": "test", "levelno": logging.INFO, "levelname": "INFO", **record_kwargs})
    return json.loads(JsonFormatter(service).format(record))


def test_schema_has_required_fields():
    out = _format({"msg": "hello"})
    assert REQUIRED_FIELDS <= set(out)
    assert out["service"] == "backend"
    assert out["msg"] == "hello"
    # Line parses as JSON (asserted by json.loads above) — the shared schema.


def test_extras_are_promoted_to_top_level_fields():
    out = _format({"msg": "ingest", "file_id": "abc_polls", "device_ip": "10.0.0.1"})
    assert out["file_id"] == "abc_polls"
    assert out["device_ip"] == "10.0.0.1"


def test_correlation_id_contextvar_roundtrip():
    set_correlation_id("fixed-id")
    assert get_correlation_id() == "fixed-id"
    assert correlation_headers() == {CORRELATION_HEADER: "fixed-id"}
    minted = new_correlation_id()
    assert minted and minted != "fixed-id"
    assert _format({"msg": "x"})["correlation_id"] == minted


def test_vendored_copies_match_shared_source():
    source = (REPO / "shared" / "logging_json.py").read_bytes()
    for service in ("backend", "manager", "agent"):
        assert (REPO / service / "logging_json.py").read_bytes() == source, f"{service} copy drifted"


def test_middleware_echoes_and_propagates_correlation_id(client):
    # A caller-supplied id is echoed back unchanged...
    resp = client.get("/health", headers={CORRELATION_HEADER: "trace-123"})
    assert resp.headers.get(CORRELATION_HEADER) == "trace-123"
    # ...and one is minted when the caller sends none.
    resp = client.get("/health")
    assert resp.headers.get(CORRELATION_HEADER)
