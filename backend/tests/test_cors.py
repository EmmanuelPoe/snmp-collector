"""CORS tightening (Step 1.6 / plan Step 18): only the methods and headers the
API actually uses are allowed in preflight."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

import config
import pytest

config.settings.database_url = "sqlite:///:memory:"

from fastapi.testclient import TestClient

ORIGIN = "http://localhost"


@pytest.fixture(scope="function")
def client(monkeypatch):
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-test-key-1234567")
    monkeypatch.setattr(config.settings, "frontend_url", ORIGIN)
    from main import app

    with TestClient(app) as c:
        yield c


def _preflight(client, method, headers=None):
    req_headers = {"Origin": ORIGIN, "Access-Control-Request-Method": method}
    if headers:
        req_headers["Access-Control-Request-Headers"] = headers
    return client.options("/devices", headers=req_headers)


def test_allowed_method_and_headers_pass_preflight(client):
    resp = _preflight(client, "PUT", "authorization, content-type")
    assert resp.status_code == 200
    allowed = resp.headers["access-control-allow-methods"]
    assert "PUT" in allowed and "DELETE" in allowed
    assert "PATCH" not in allowed


def test_disallowed_method_rejected(client):
    resp = _preflight(client, "PATCH")
    assert resp.status_code == 400


def test_disallowed_header_rejected(client):
    resp = _preflight(client, "GET", "x-custom-header")
    assert resp.status_code == 400
