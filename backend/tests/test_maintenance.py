"""Tests for maintenance windows (router CRUD + evaluator suppression)."""
from datetime import datetime, timedelta, timezone

import pytest

import alert_evaluator
from auth import hash_password
from models import (
    Alert, AlertStatus, AlertType, Device, MaintenanceWindow, User, UserRole,
)


@pytest.fixture(autouse=True)
def _reset_suppression():
    """Prevent module-level suppression state leaking between tests."""
    yield
    alert_evaluator._suppress_all = False
    alert_evaluator._suppressed_devices = set()


def _iso(dt):
    return dt.isoformat()


# --- router ---

def test_list_windows_empty(client, admin_headers):
    r = client.get("/maintenance-windows", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_global_window(client, admin_headers):
    now = datetime.now(timezone.utc)
    r = client.post("/maintenance-windows", json={
        "start_at": _iso(now), "end_at": _iso(now + timedelta(hours=1)), "reason": "patching",
    }, headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["device_id"] is None
    assert r.json()["reason"] == "patching"


def test_create_window_end_before_start_rejected(client, admin_headers):
    now = datetime.now(timezone.utc)
    r = client.post("/maintenance-windows", json={
        "start_at": _iso(now), "end_at": _iso(now - timedelta(hours=1)),
    }, headers=admin_headers)
    assert r.status_code == 422


def test_create_window_unknown_device_rejected(client, admin_headers):
    now = datetime.now(timezone.utc)
    r = client.post("/maintenance-windows", json={
        "device_id": 9999, "start_at": _iso(now), "end_at": _iso(now + timedelta(hours=1)),
    }, headers=admin_headers)
    assert r.status_code == 404


def test_active_only_filter(client, admin_headers, db_session):
    now = datetime.now(timezone.utc)
    db_session.add(MaintenanceWindow(start_at=now - timedelta(hours=2), end_at=now - timedelta(hours=1)))  # past
    db_session.add(MaintenanceWindow(start_at=now - timedelta(minutes=5), end_at=now + timedelta(hours=1)))  # active
    db_session.commit()
    r = client.get("/maintenance-windows", params={"active_only": "true"}, headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_delete_window(client, admin_headers, db_session):
    now = datetime.now(timezone.utc)
    w = MaintenanceWindow(start_at=now, end_at=now + timedelta(hours=1))
    db_session.add(w)
    db_session.commit()
    assert client.delete(f"/maintenance-windows/{w.id}", headers=admin_headers).status_code == 204


def test_viewer_cannot_create_window(client, db_session):
    db_session.add(User(email="v@test.com", hashed_password=hash_password("pw"),
                        role=UserRole.viewer, is_active=True, force_password_change=False))
    db_session.commit()
    token = client.post("/auth/login", data={"username": "v@test.com", "password": "pw"}).json()["access_token"]
    now = datetime.now(timezone.utc)
    r = client.post("/maintenance-windows",
                    json={"start_at": _iso(now), "end_at": _iso(now + timedelta(hours=1))},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_windows_require_auth(client):
    assert client.get("/maintenance-windows").status_code == 401


# --- evaluator suppression ---

def _open_count(db, device_id=None):
    q = db.query(Alert).filter(Alert.status == AlertStatus.open)
    if device_id is not None:
        q = q.filter(Alert.device_id == device_id)
    return q.count()


def test_device_window_suppresses_new_alert(db_session):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()
    now = datetime.now(timezone.utc)
    db_session.add(MaintenanceWindow(device_id=device.id,
                                     start_at=now - timedelta(minutes=1),
                                     end_at=now + timedelta(hours=1)))
    db_session.commit()

    alert_evaluator._load_suppression(db_session)
    alert_evaluator._create_alert(db_session, AlertType.interface_down, "down", device_id=device.id)
    db_session.commit()
    assert _open_count(db_session, device.id) == 0


def test_device_window_does_not_suppress_other_devices(db_session):
    d1 = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    d2 = Device(name="d2", ip_address="10.0.0.2", enabled=True)
    db_session.add_all([d1, d2])
    db_session.commit()
    now = datetime.now(timezone.utc)
    db_session.add(MaintenanceWindow(device_id=d1.id,
                                     start_at=now - timedelta(minutes=1),
                                     end_at=now + timedelta(hours=1)))
    db_session.commit()

    alert_evaluator._load_suppression(db_session)
    alert_evaluator._create_alert(db_session, AlertType.interface_down, "down", device_id=d2.id)
    db_session.commit()
    assert _open_count(db_session, d2.id) == 1


def test_global_window_suppresses_agent_alert(db_session):
    now = datetime.now(timezone.utc)
    db_session.add(MaintenanceWindow(device_id=None,
                                     start_at=now - timedelta(minutes=1),
                                     end_at=now + timedelta(hours=1)))
    db_session.commit()

    alert_evaluator._load_suppression(db_session)
    alert_evaluator._create_alert(db_session, AlertType.agent_offline, "agent gone", agent_id="a1")
    db_session.commit()
    assert _open_count(db_session) == 0


def test_expired_window_does_not_suppress(db_session):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()
    now = datetime.now(timezone.utc)
    db_session.add(MaintenanceWindow(device_id=device.id,
                                     start_at=now - timedelta(hours=2),
                                     end_at=now - timedelta(hours=1)))
    db_session.commit()

    alert_evaluator._load_suppression(db_session)
    alert_evaluator._create_alert(db_session, AlertType.interface_down, "down", device_id=device.id)
    db_session.commit()
    assert _open_count(db_session, device.id) == 1


def test_suppression_blocks_creation_not_resolution(db_session):
    """Suppress-new-only: an already-open alert must still be resolvable."""
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()
    db_session.add(Alert(alert_type=AlertType.interface_down, message="old",
                         device_id=device.id, status=AlertStatus.open))
    now = datetime.now(timezone.utc)
    db_session.add(MaintenanceWindow(device_id=device.id,
                                     start_at=now - timedelta(minutes=1),
                                     end_at=now + timedelta(hours=1)))
    db_session.commit()

    alert_evaluator._load_suppression(db_session)
    alert_evaluator._resolve_alerts(db_session, AlertType.interface_down, device_id=device.id)
    db_session.commit()
    assert _open_count(db_session, device.id) == 0
