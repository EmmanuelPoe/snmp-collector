"""Password strength policy (Step 6.1)."""

import pytest
from config import settings
from password_policy import PasswordPolicyError, validate_password


def test_accepts_a_strong_password():
    validate_password("correct-horse-battery-staple", email="alice@example.com")


def test_rejects_too_short():
    with pytest.raises(PasswordPolicyError, match="at least"):
        validate_password("short1", email="a@b.com")


def test_rejects_common_password():
    # Long enough to pass length, but a well-known guess.
    with pytest.raises(PasswordPolicyError, match="commonly used"):
        validate_password("qwertyuiop", email="a@b.com")


def test_rejects_containing_email_local_part():
    with pytest.raises(PasswordPolicyError, match="email name"):
        validate_password("alicesmith-2026-xy", email="alicesmith@example.com")


def test_character_classes_enforced_only_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "password_require_classes", True)
    with pytest.raises(PasswordPolicyError, match="three of"):
        validate_password("alllowercaseletters", email=None)
    validate_password("MixedCase123!extra", email=None)  # 4 classes → ok
