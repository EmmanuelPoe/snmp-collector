import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Set env vars before any app modules are imported so Settings() can instantiate
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")
os.environ.setdefault("MANAGER_API_KEY", "test-manager-api-key")
# Rate limiting off by default so unrelated tests can hammer endpoints freely;
# tests/test_rate_limit.py re-enables the limiter explicitly.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

# Override database_url to SQLite before database.py is imported and creates its engine
import config

config.settings.database_url = "sqlite:///./test_bootstrap.db"

import models  # noqa: F401  — populate Base.metadata before create_all below
import pytest
from database import Base, engine as _bootstrap_engine, get_db

# The lifespan bootstrap (admin seeding) runs against the module-level engine
# (test_bootstrap.db). Step 2.2 made a failing bootstrap abort startup instead
# of being swallowed — so give that engine real tables.
Base.metadata.create_all(bind=_bootstrap_engine)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def db_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")

    import config

    config.settings.database_url = "sqlite:///:memory:"

    from main import app

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_headers(client, db_session):
    """Return Authorization headers for a seeded admin user."""
    from auth import hash_password
    from models import User, UserRole

    admin = User(
        email="admin@test.com",
        hashed_password=hash_password("testpass"),
        role=UserRole.admin,
        force_password_change=False,
    )
    db_session.add(admin)
    db_session.commit()
    resp = client.post("/auth/login", data={"username": "admin@test.com", "password": "testpass"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
