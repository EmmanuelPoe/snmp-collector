import pytest

import config
from config import check_required_secrets

_STRONG = "a-strong-unique-secret-123"


def _set(monkeypatch, jwt=_STRONG, mgr=_STRONG, enc=None):
    monkeypatch.setattr(config.settings, "jwt_secret", jwt)
    monkeypatch.setattr(config.settings, "manager_api_key", mgr)
    monkeypatch.setattr(config.settings, "encryption_key", enc)


def test_strong_secrets_pass(monkeypatch):
    _set(monkeypatch)
    check_required_secrets()  # no raise


def test_placeholder_manager_key_rejected(monkeypatch):
    _set(monkeypatch, mgr="change-me-in-production")
    with pytest.raises(RuntimeError, match="MANAGER_API_KEY"):
        check_required_secrets()


def test_placeholder_jwt_secret_rejected(monkeypatch):
    _set(monkeypatch, jwt="replace-with-a-long-random-secret")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        check_required_secrets()


def test_short_secret_rejected(monkeypatch):
    _set(monkeypatch, jwt="short")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        check_required_secrets()


def test_unset_manager_key_rejected(monkeypatch):
    _set(monkeypatch, mgr="")
    with pytest.raises(RuntimeError, match="MANAGER_API_KEY is not set"):
        check_required_secrets()


def test_empty_encryption_key_allowed(monkeypatch):
    # Empty ENCRYPTION_KEY is valid — a key is derived from JWT_SECRET.
    _set(monkeypatch, enc="")
    check_required_secrets()  # no raise


def test_placeholder_encryption_key_rejected(monkeypatch):
    _set(monkeypatch, enc="changeme")
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        check_required_secrets()
