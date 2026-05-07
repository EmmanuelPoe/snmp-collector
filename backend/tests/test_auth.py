import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from unittest.mock import MagicMock
import config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
config.settings.database_url = "sqlite:///:memory:"
config.settings.jwt_secret = "test-secret"

from auth import hash_password, verify_password, create_access_token, get_current_user, require_role, require_manager_key
from database import get_db
from jose import jwt
from fastapi import HTTPException
from models import User, UserRole


def test_hash_and_verify_password():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed)
    assert not verify_password("wrong", hashed)


def test_create_access_token_contains_sub():
    token = create_access_token({"sub": "user@example.com", "role": "viewer"})
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["sub"] == "user@example.com"
    assert payload["role"] == "viewer"


def test_require_role_raises_for_insufficient_role():
    user = User(email="e@e.com", hashed_password="x", role=UserRole.viewer, is_active=True)
    dep = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dep(current_user=user)
    assert exc.value.status_code == 403


def test_require_role_passes_for_correct_role():
    user = User(email="a@a.com", hashed_password="x", role=UserRole.admin, is_active=True)
    dep = require_role("admin", "editor")
    result = dep(current_user=user)
    assert result.email == "a@a.com"


def test_require_manager_key_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(config.settings, "manager_api_key", "real-key")
    with pytest.raises(HTTPException) as exc:
        require_manager_key(authorization="Bearer wrong-key")
    assert exc.value.status_code == 401


def test_require_manager_key_accepts_correct_key(monkeypatch):
    monkeypatch.setattr(config.settings, "manager_api_key", "real-key")
    result = require_manager_key(authorization="Bearer real-key")
    assert result is True


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/auth.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_current_user_rejects_invalid_token(db):
    from auth import get_current_user
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        get_current_user(token="not-a-valid-token", db=db)
    assert exc.value.status_code == 401


def test_get_current_user_rejects_expired_token(db):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    expired_payload = {"sub": "user@test.com", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}
    expired_token = jwt.encode(expired_payload, "test-secret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        get_current_user(token=expired_token, db=db)
    assert exc.value.status_code == 401


def test_get_current_user_rejects_missing_sub(db):
    token = create_access_token({"role": "viewer"})  # no "sub"
    with pytest.raises(HTTPException) as exc:
        get_current_user(token=token, db=db)
    assert exc.value.status_code == 401


def test_get_current_user_rejects_nonexistent_user(db):
    token = create_access_token({"sub": "ghost@test.com", "role": "viewer"})
    with pytest.raises(HTTPException) as exc:
        get_current_user(token=token, db=db)
    assert exc.value.status_code == 401


def test_get_current_user_returns_user(db):
    from models import User, UserRole
    user = User(email="real@test.com", hashed_password=hash_password("pw"), role=UserRole.viewer, is_active=True)
    db.add(user)
    db.commit()
    token = create_access_token({"sub": "real@test.com", "role": "viewer"})
    result = get_current_user(token=token, db=db)
    assert result.email == "real@test.com"


def test_require_manager_key_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(config.settings, "manager_api_key", "real-key")
    with pytest.raises(HTTPException) as exc:
        require_manager_key(authorization=None)
    assert exc.value.status_code == 401


# ---- Router-level tests (need full app client) ----

from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-key")
    monkeypatch.setattr(config.settings, "frontend_url", "http://localhost")
    db_url = f"sqlite:///{tmp_path}/auth_test.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    from main import app
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()


def test_login_with_seeded_admin(auth_client):
    resp = auth_client.post("/auth/login", data={"username": "admin@localhost", "password": "admin"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(auth_client):
    resp = auth_client.post("/auth/login", data={"username": "admin@localhost", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_auth(auth_client):
    resp = auth_client.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(auth_client):
    login = auth_client.post("/auth/login", data={"username": "admin@localhost", "password": "admin"})
    token = login.json()["access_token"]
    resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@localhost"
    assert resp.json()["role"] == "admin"


def test_register_requires_admin(auth_client):
    resp = auth_client.post("/auth/register", json={"email": "new@x.com", "password": "pw", "role": "viewer"})
    assert resp.status_code == 401


def test_register_creates_user(auth_client):
    login = auth_client.post("/auth/login", data={"username": "admin@localhost", "password": "admin"})
    token = login.json()["access_token"]
    resp = auth_client.post(
        "/auth/register",
        json={"email": "editor@x.com", "password": "pw123", "role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "editor"
