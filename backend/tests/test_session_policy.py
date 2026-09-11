"""Step 38 (roadmap 6.1): /auth/refresh sliding idle window + absolute session cap."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from auth import create_access_token, hash_password
from config import settings
from jose import jwt
from models import User, UserRole

EMAIL = "session@test.com"
PASSWORD = "correct-horse-battery-staple"


def _make_user(db_session):
    user = User(
        email=EMAIL,
        hashed_password=hash_password(PASSWORD),
        role=UserRole.viewer,
        force_password_change=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _login(client):
    resp = client.post("/auth/login", data={"username": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _claims(token):
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def test_refresh_issues_working_token_and_preserves_session_start(client, db_session):
    _make_user(db_session)
    token = _login(client)
    original_sst = _claims(token)["sst"]

    resp = client.post("/auth/refresh", headers=_auth(token))
    assert resp.status_code == 200
    new_token = resp.json()["access_token"]

    assert new_token != token
    assert client.get("/auth/me", headers=_auth(new_token)).status_code == 200
    # Session start is preserved so repeated refreshes can never push the session
    # past the absolute cap.
    assert _claims(new_token)["sst"] == original_sst


def test_refresh_is_bounded_by_absolute_cap(client, db_session):
    user = _make_user(db_session)
    # A session that started (absolute_hours - 30s) ago: still valid, but only ~30s
    # remain before the absolute cap — far less than a full idle window.
    now = int(datetime.now(timezone.utc).timestamp())
    old_sst = now - (settings.session_absolute_hours * 3600 - 30)
    token = create_access_token(
        {"sub": EMAIL, "role": user.role, "ver": user.token_version or 0},
        session_start=old_sst,
    )

    resp = client.post("/auth/refresh", headers=_auth(token))
    assert resp.status_code == 200
    new_exp = _claims(resp.json()["access_token"])["exp"]

    cap = old_sst + settings.session_absolute_hours * 3600
    # Refreshed token expires at the cap, not a fresh idle window from now.
    assert new_exp <= cap
    assert new_exp < now + settings.session_idle_minutes * 60


def test_refresh_rejects_logged_out_token(client, db_session):
    _make_user(db_session)
    token = _login(client)
    assert client.post("/auth/logout", headers=_auth(token)).status_code == 204
    # A revoked token is rejected upstream by the version/denylist check.
    assert client.post("/auth/refresh", headers=_auth(token)).status_code == 401
