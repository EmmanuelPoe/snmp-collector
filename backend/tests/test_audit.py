import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests")

from datetime import datetime, timedelta, timezone

import config
import pytest

config.settings.database_url = "sqlite:///:memory:"
config.settings.jwt_secret = "test-secret-for-unit-tests"

from audit import REDACTED, prune_old_entries
from auth import hash_password
from database import Base, get_db
from fastapi.testclient import TestClient
from models import Alert, AlertStatus, AlertType, AuditLog, User, UserRole
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/audit.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    admin = User(
        email="admin@test.com",
        hashed_password=hash_password("pw"),
        role=UserRole.admin,
        is_active=True,
        force_password_change=False,
    )
    viewer = User(
        email="viewer@test.com",
        hashed_password=hash_password("pw"),
        role=UserRole.viewer,
        is_active=True,
        force_password_change=False,
    )
    session.add_all([admin, viewer])
    session.commit()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(session, monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", "test-secret-for-unit-tests")
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-test-key-1234567")
    from main import app

    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    resp = client.post("/auth/login", data={"username": "admin@test.com", "password": "pw"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def viewer_auth(client):
    resp = client.post("/auth/login", data={"username": "viewer@test.com", "password": "pw"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _entries(session, action):
    return session.query(AuditLog).filter(AuditLog.action == action).all()


# ---- auth events ----


def test_login_success_recorded(client, session, auth):
    rows = _entries(session, "auth.login")
    assert len(rows) == 1
    admin = session.query(User).filter(User.email == "admin@test.com").first()
    assert rows[0].actor_user_id == admin.id
    assert rows[0].actor_email == "admin@test.com"


def test_login_failure_recorded_with_null_actor_and_source_ip(client, session):
    resp = client.post(
        "/auth/login", data={"username": "nobody@test.com", "password": "wrong"}, headers={"X-Real-IP": "203.0.113.9"}
    )
    assert resp.status_code == 401
    rows = _entries(session, "auth.login_failed")
    assert len(rows) == 1
    assert rows[0].actor_user_id is None
    assert rows[0].actor_email == "nobody@test.com"
    assert rows[0].source_ip == "203.0.113.9"


def test_login_failure_wrong_password_recorded(client, session):
    resp = client.post("/auth/login", data={"username": "admin@test.com", "password": "wrong"})
    assert resp.status_code == 401
    assert len(_entries(session, "auth.login_failed")) == 1


def test_logout_recorded(client, session, auth):
    assert client.post("/auth/logout", headers=auth).status_code == 204
    rows = _entries(session, "auth.logout")
    assert len(rows) == 1
    assert rows[0].actor_email == "admin@test.com"
    assert rows[0].actor_user_id is not None


def test_change_password_recorded(client, session, auth):
    resp = client.post(
        "/auth/change-password", json={"current_password": "pw", "new_password": "newpassword1"}, headers=auth
    )
    assert resp.status_code == 200
    rows = _entries(session, "auth.password_changed")
    assert len(rows) == 1
    # The summary must never contain password values.
    assert rows[0].summary is None


def test_register_user_recorded(client, session, auth):
    resp = client.post(
        "/auth/register",
        json={"email": "new@test.com", "password": "Zx9-Vault-Panda-Meadow", "role": "viewer"},
        headers=auth,
    )
    assert resp.status_code == 201
    rows = _entries(session, "user.create")
    assert len(rows) == 1
    assert rows[0].target_type == "user"
    assert rows[0].summary == {"email": "new@test.com", "role": "viewer"}
    assert "password" not in rows[0].summary


# ---- device events + credential redaction ----


def test_device_create_redacts_credentials(client, session, auth):
    resp = client.post(
        "/devices",
        json={
            "name": "sw1",
            "ip_address": "10.0.0.1",
            "snmp_community": "s3cret",
        },
        headers=auth,
    )
    assert resp.status_code == 201
    rows = _entries(session, "device.create")
    assert len(rows) == 1
    assert rows[0].target_type == "device"
    assert rows[0].summary["name"] == "sw1"
    assert rows[0].summary["snmp_community"] == REDACTED


def test_device_update_summary_has_field_names_never_credential_values(client, session, auth):
    device_id = client.post("/devices", json={"name": "sw2", "ip_address": "10.0.0.2"}, headers=auth).json()["id"]
    resp = client.put(
        f"/devices/{device_id}",
        json={
            "description": "core switch",
            "snmp_community": "supersecret",
            "auth_password": "authsecret",
            "priv_password": "privsecret",
        },
        headers=auth,
    )
    assert resp.status_code == 200
    rows = _entries(session, "device.update")
    assert len(rows) == 1
    summary = rows[0].summary
    assert set(summary) == {"description", "snmp_community", "auth_password", "priv_password"}
    assert summary["description"] == "core switch"
    for field in ("snmp_community", "auth_password", "priv_password"):
        assert summary[field] == REDACTED
    assert "supersecret" not in str(summary)
    assert "authsecret" not in str(summary)
    assert "privsecret" not in str(summary)


def test_device_delete_recorded(client, session, auth):
    device_id = client.post("/devices", json={"name": "sw3", "ip_address": "10.0.0.3"}, headers=auth).json()["id"]
    assert client.delete(f"/devices/{device_id}", headers=auth).status_code == 204
    rows = _entries(session, "device.delete")
    assert len(rows) == 1
    assert rows[0].target_id == str(device_id)
    assert rows[0].summary == {"name": "sw3", "ip_address": "10.0.0.3"}


# ---- config events ----


def test_config_crud_recorded(client, session, auth):
    config_id = client.post(
        "/config/configs",
        json={
            "oid": "1.3.6.1.2.1.1.1.0",
            "oid_name": "sysDescr",
        },
        headers=auth,
    ).json()["id"]
    client.put(f"/config/configs/{config_id}", json={"enabled": False}, headers=auth)
    client.delete(f"/config/configs/{config_id}", headers=auth)
    assert len(_entries(session, "config.create")) == 1
    update_rows = _entries(session, "config.update")
    assert len(update_rows) == 1
    assert update_rows[0].summary == {"enabled": False}
    assert len(_entries(session, "config.delete")) == 1


# ---- alert events ----


def test_alert_actions_recorded(client, session, auth):
    alert = Alert(alert_type=AlertType.device_unreachable, message="down", status=AlertStatus.open)
    session.add(alert)
    session.commit()
    admin = session.query(User).filter(User.email == "admin@test.com").first()
    assert client.put(f"/alerts/{alert.id}/acknowledge", headers=auth).status_code == 200
    assert client.put(f"/alerts/{alert.id}/assign", json={"assigned_to": admin.id}, headers=auth).status_code == 200
    assert client.put(f"/alerts/{alert.id}/note", json={"note": "looking"}, headers=auth).status_code == 200
    assert client.put(f"/alerts/{alert.id}/resolve", headers=auth).status_code == 200
    for action in ("alert.acknowledge", "alert.assign", "alert.note", "alert.resolve"):
        rows = _entries(session, action)
        assert len(rows) == 1, action
        assert rows[0].target_id == str(alert.id)
    assert _entries(session, "alert.assign")[0].summary == {"assigned_to": admin.id}


def test_alert_rule_upsert_recorded(client, session, auth):
    device_id = client.post("/devices", json={"name": "sw4", "ip_address": "10.0.0.4"}, headers=auth).json()["id"]
    resp = client.post(f"/alert-rules/{device_id}", json={"bandwidth_in_pct": 80}, headers=auth)
    assert resp.status_code == 200
    rows = _entries(session, "alert_rule.upsert")
    assert len(rows) == 1
    assert rows[0].summary == {"bandwidth_in_pct": 80.0}


# ---- notification channels (webhook URL is a secret) ----


def test_notification_channel_create_redacts_url(client, session, auth):
    resp = client.post(
        "/notification-channels",
        json={
            "name": "ops",
            "type": "slack",
            "url": "https://hooks.slack.com/services/T0/B0/secret",
        },
        headers=auth,
    )
    assert resp.status_code == 201
    rows = _entries(session, "notification_channel.create")
    assert len(rows) == 1
    assert rows[0].summary["url"] == REDACTED
    assert "hooks.slack.com" not in str(rows[0].summary)


# ---- maintenance windows ----


def test_maintenance_window_create_and_delete_recorded(client, session, auth):
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    window_id = client.post(
        "/maintenance-windows",
        json={
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "reason": "patching",
        },
        headers=auth,
    ).json()["id"]
    assert client.delete(f"/maintenance-windows/{window_id}", headers=auth).status_code == 204
    assert len(_entries(session, "maintenance_window.create")) == 1
    delete_rows = _entries(session, "maintenance_window.delete")
    assert len(delete_rows) == 1
    assert delete_rows[0].summary["reason"] == "patching"


# ---- GET /audit ----


def test_audit_endpoint_admin_only(client, viewer_auth):
    resp = client.get("/audit", headers=viewer_auth)
    assert resp.status_code == 403


def test_audit_endpoint_requires_auth(client):
    assert client.get("/audit").status_code == 401


def test_audit_endpoint_lists_filters_and_paginates(client, session, auth):
    client.post("/devices", json={"name": "sw5", "ip_address": "10.0.0.5"}, headers=auth)
    client.post("/auth/login", data={"username": "ghost@test.com", "password": "x"})

    resp = client.get("/audit", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3  # login + device.create + login_failed
    actions = [e["action"] for e in body["items"]]
    assert "device.create" in actions
    assert "auth.login_failed" in actions

    # Filter by action
    resp = client.get("/audit", params={"action": "device.create"}, headers=auth)
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_type"] == "device"

    # Filter by actor
    resp = client.get("/audit", params={"actor_email": "ghost@test.com"}, headers=auth)
    assert resp.json()["total"] == 1

    # Pagination
    resp = client.get("/audit", params={"limit": 1, "offset": 0}, headers=auth)
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] >= 3


# ---- retention ----


def test_prune_old_entries(session):
    old = AuditLog(action="auth.login", created_at=datetime.now(timezone.utc) - timedelta(days=500))
    recent = AuditLog(action="auth.login", created_at=datetime.now(timezone.utc) - timedelta(days=5))
    session.add_all([old, recent])
    session.commit()
    deleted = prune_old_entries(session, retention_days=400)
    assert deleted == 1
    remaining = session.query(AuditLog).all()
    assert len(remaining) == 1
