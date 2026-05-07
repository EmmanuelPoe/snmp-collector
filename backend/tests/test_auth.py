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
config.settings.database_url = "sqlite:///./test_auth_bootstrap.db"
config.settings.jwt_secret = "test-secret"

from auth import hash_password, verify_password, create_access_token, get_current_user, require_role, require_manager_key
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
