"""Step 2.2: a dead Postgres fails backend startup loudly instead of starting
'healthy' with a broken database."""

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
from sqlalchemy.exc import OperationalError


def test_startup_aborts_when_postgres_unreachable(monkeypatch):
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-test-key-1234567")
    import logging

    import main

    class DeadSession:
        def query(self, *a, **k):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def close(self):
            pass

    monkeypatch.setattr(main, "SessionLocal", lambda: DeadSession())

    # main's logging setup uses force=True, which strips pytest's caplog
    # handler — capture on the module logger directly instead.
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logging.getLogger("main").addHandler(handler)
    try:
        with pytest.raises(OperationalError):
            with TestClient(main.app):
                pass
    finally:
        logging.getLogger("main").removeHandler(handler)
    assert any("unreachable at startup" in r.getMessage() for r in records)
