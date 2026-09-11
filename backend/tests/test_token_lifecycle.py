"""Step 16 (roadmap 1.4): token revocation, logout, version-stale rejection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone

from auth import hash_password
from models import RevokedToken, User, UserRole

EMAIL = "lifecycle@test.com"
PASSWORD = "correct-horse-battery"


def _make_user(db_session, email=EMAIL, password=PASSWORD, **kwargs):
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.viewer,
        force_password_change=False,
        **kwargs,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _login(client, email=EMAIL, password=PASSWORD):
    resp = client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_logout_revokes_token(client, db_session):
    _make_user(db_session)
    token = _login(client)
    assert client.get("/auth/me", headers=_auth(token)).status_code == 200
    assert client.post("/auth/logout", headers=_auth(token)).status_code == 204
    assert client.get("/auth/me", headers=_auth(token)).status_code == 401


def test_logout_leaves_other_sessions_intact(client, db_session):
    _make_user(db_session)
    token_a = _login(client)
    token_b = _login(client)
    client.post("/auth/logout", headers=_auth(token_a))
    assert client.get("/auth/me", headers=_auth(token_a)).status_code == 401
    assert client.get("/auth/me", headers=_auth(token_b)).status_code == 200


def test_relogin_after_logout_issues_working_token(client, db_session):
    _make_user(db_session)
    token = _login(client)
    client.post("/auth/logout", headers=_auth(token))
    fresh = _login(client)
    assert client.get("/auth/me", headers=_auth(fresh)).status_code == 200


def test_password_change_invalidates_old_tokens(client, db_session):
    _make_user(db_session)
    old_token = _login(client)
    other_session = _login(client)
    resp = client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-new-password-123"},
        headers=_auth(old_token),
    )
    assert resp.status_code == 200
    fresh = resp.json()["access_token"]
    # Every pre-change token is version-stale; the returned one works.
    assert client.get("/auth/me", headers=_auth(old_token)).status_code == 401
    assert client.get("/auth/me", headers=_auth(other_session)).status_code == 401
    assert client.get("/auth/me", headers=_auth(fresh)).status_code == 200


def test_deactivated_user_token_rejected(client, db_session):
    user = _make_user(db_session)
    token = _login(client)
    user.is_active = False
    db_session.commit()
    assert client.get("/auth/me", headers=_auth(token)).status_code == 401


def test_logout_prunes_expired_denylist_rows(client, db_session):
    _make_user(db_session)
    db_session.add(RevokedToken(jti="stale-jti", expires_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    db_session.commit()
    token = _login(client)
    client.post("/auth/logout", headers=_auth(token))
    remaining = {t.jti for t in db_session.query(RevokedToken).all()}
    assert "stale-jti" not in remaining
    assert len(remaining) == 1  # only the just-revoked token


def test_logout_with_garbage_token_is_401(client, db_session):
    assert client.post("/auth/logout", headers=_auth("not-a-jwt")).status_code == 401
