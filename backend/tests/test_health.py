"""Liveness/readiness split (Step 2.3 / plan Step 27)."""

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

config.settings.database_url = "sqlite:///./test_bootstrap.db"

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-test-key-1234567")
    from main import app

    with TestClient(app) as c:
        yield c


def test_live_and_health_alias_are_static_200(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health").status_code == 200


def test_ready_200_with_reachable_postgres(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["postgres"] == "ok"
    # The manager is not running in unit tests — reported, not fatal.
    assert body["manager"] == "unreachable"


def test_ready_503_when_postgres_dead(client, monkeypatch):
    import main

    class DeadSession:
        def execute(self, *a, **k):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def close(self):
            pass

    monkeypatch.setattr(main, "SessionLocal", lambda: DeadSession())
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["status"] == "unready"
    # Liveness is unaffected.
    assert client.get("/health/live").status_code == 200
