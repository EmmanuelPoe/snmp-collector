"""Step 15 (roadmap 1.3): rate limiting + login lockout."""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone

import pytest

import config
from auth import hash_password
from models import User, UserRole
from rate_limit import limiter

EMAIL = "user@test.com"
PASSWORD = "correct-horse-battery"


def _make_user(db_session, email=EMAIL, password=PASSWORD):
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.viewer,
        force_password_change=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _login(client, password, email=EMAIL):
    return client.post("/auth/login", data={"username": email, "password": password})


@pytest.fixture
def low_lockout_threshold(monkeypatch):
    """Shrink the threshold so tests don't pay for 10 bcrypt verifications."""
    monkeypatch.setattr(config.settings, "login_lockout_threshold", 3)


# ---------------------------------------------------------------- lockout

def test_lockout_after_repeated_failures(client, db_session, low_lockout_threshold):
    _make_user(db_session)
    for _ in range(3):
        assert _login(client, "wrong").status_code == 401
    # Even the correct password is now rejected with 423 + Retry-After.
    resp = _login(client, PASSWORD)
    assert resp.status_code == 423
    assert int(resp.headers["Retry-After"]) > 0


def test_lockout_expires(client, db_session):
    user = _make_user(db_session)
    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    resp = _login(client, PASSWORD)
    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.locked_until is None
    assert user.failed_login_count == 0


def test_active_lockout_rejects_before_password_check(client, db_session):
    user = _make_user(db_session)
    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
    db_session.commit()
    # Wrong password while locked must not leak signal: same 423, and the
    # failure counter must not advance.
    resp = _login(client, "wrong")
    assert resp.status_code == 423
    db_session.refresh(user)
    assert user.failed_login_count == 0


def test_success_resets_failure_counter(client, db_session, low_lockout_threshold):
    user = _make_user(db_session)
    for _ in range(2):
        _login(client, "wrong")
    db_session.refresh(user)
    assert user.failed_login_count == 2
    assert _login(client, PASSWORD).status_code == 200
    db_session.refresh(user)
    assert user.failed_login_count == 0
    # Counter starts fresh — two more failures do not lock (threshold 3).
    for _ in range(2):
        _login(client, "wrong")
    assert _login(client, PASSWORD).status_code == 200


def test_unknown_email_is_plain_401(client, db_session):
    assert _login(client, "whatever", email="ghost@test.com").status_code == 401


# ---------------------------------------------------------------- rate limit

@pytest.fixture
def rate_limiter_on():
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_login_rate_limited_per_ip(client, db_session, rate_limiter_on, monkeypatch):
    monkeypatch.setattr(config.settings, "login_rate_limit", "5/minute")
    # Unknown user → no bcrypt cost, no lockout interference.
    statuses = [_login(client, "x", email="ghost@test.com").status_code for _ in range(7)]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
    assert statuses[6] == 429


def test_rate_limit_keys_on_x_real_ip(client, db_session, rate_limiter_on, monkeypatch):
    monkeypatch.setattr(config.settings, "login_rate_limit", "3/minute")
    for _ in range(3):
        client.post("/auth/login", data={"username": "a@test.com", "password": "x"},
                    headers={"X-Real-IP": "10.0.0.1"})
    blocked = client.post("/auth/login", data={"username": "a@test.com", "password": "x"},
                          headers={"X-Real-IP": "10.0.0.1"})
    assert blocked.status_code == 429
    # A different client IP is unaffected.
    other = client.post("/auth/login", data={"username": "a@test.com", "password": "x"},
                        headers={"X-Real-IP": "10.0.0.2"})
    assert other.status_code == 401


def test_walk_rate_limited_per_token(client, db_session, admin_headers, rate_limiter_on, monkeypatch):
    monkeypatch.setattr(config.settings, "walk_rate_limit", "2/minute")
    # Nonexistent device → cheap 404s, but the limiter still counts them.
    statuses = [
        client.post("/devices/9999/walk", headers=admin_headers).status_code
        for _ in range(4)
    ]
    assert statuses[:2] == [404, 404]
    assert 429 in statuses[2:]
