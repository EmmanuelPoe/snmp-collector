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


def test_startup_survives_bootstrap_admin_race(monkeypatch):
    """The image starts uvicorn with --workers 2, so the lifespan's
    count()-then-insert bootstrap runs once per worker and races on a fresh
    database. The worker that loses must roll back and carry on — raising took
    the whole backend down, which surfaced as nginx failing to resolve
    `backend` and the e2e login POST never landing."""
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-test-key-1234567")
    import logging

    import main
    from sqlalchemy.exc import IntegrityError

    class RacingSession:
        """Reports an empty users table, then rejects the insert the way the
        users_email_key constraint does when another worker committed first."""

        def __init__(self):
            self.rolled_back = False

        def query(self, *a, **k):
            return self

        def count(self):
            return 0

        def add(self, obj):
            pass

        def commit(self):
            raise IntegrityError(
                "INSERT INTO users",
                {},
                Exception('duplicate key value violates unique constraint "users_email_key"'),
            )

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    session = RacingSession()
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logging.getLogger("main").addHandler(handler)
    try:
        with TestClient(main.app):
            pass
    finally:
        logging.getLogger("main").removeHandler(handler)

    assert session.rolled_back
    messages = [r.getMessage() for r in records]
    assert any("already created by another worker" in m for m in messages)
    # The loser must not print a one-time password that was never persisted —
    # the CI e2e job greps the last such line out of the backend log.
    assert not any("Bootstrap admin created" in m for m in messages)
