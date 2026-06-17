import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
import config
config.settings.database_url = "sqlite:///:memory:"
config.settings.jwt_secret = "test-secret"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from database import Base, get_db
from auth import hash_password
from models import User, UserRole, Alert, AlertRule, AlertType, AlertStatus, Device


@pytest.fixture(scope="function")
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(config.settings, "manager_api_key", "mgr-key")
    monkeypatch.setattr(config.settings, "frontend_url", "http://localhost")
    engine = create_engine(f"sqlite:///{tmp_path}/alert.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    admin = User(email="admin@test.com", hashed_password=hash_password("pw"),
                 role=UserRole.admin, is_active=True, force_password_change=False)
    viewer = User(email="viewer@test.com", hashed_password=hash_password("pw"),
                  role=UserRole.viewer, is_active=True, force_password_change=False)
    session.add_all([admin, viewer])
    session.commit()
    from main import app
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture
def admin_token(client):
    resp = client.post("/auth/login", data={"username": "admin@test.com", "password": "pw"})
    return resp.json()["access_token"]

@pytest.fixture
def viewer_token(client):
    resp = client.post("/auth/login", data={"username": "viewer@test.com", "password": "pw"})
    return resp.json()["access_token"]

@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture
def viewer_auth(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


def test_list_alerts_empty(client, auth):
    resp = client.get("/alerts", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


def test_alert_count_zero(client, auth):
    resp = client.get("/alerts/count", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"open": 0}


def test_list_alerts_returns_open_only(client, auth):
    db = client.app.dependency_overrides[get_db]()
    open_alert = Alert(alert_type=AlertType.agent_offline, message="agent down", status=AlertStatus.open)
    resolved_alert = Alert(alert_type=AlertType.agent_offline, message="agent down", status=AlertStatus.resolved)
    db.add_all([open_alert, resolved_alert])
    db.commit()
    resp = client.get("/alerts", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "open"


def test_list_alerts_include_resolved(client, auth):
    db = client.app.dependency_overrides[get_db]()
    db.add_all([
        Alert(alert_type=AlertType.agent_offline, message="a", status=AlertStatus.open),
        Alert(alert_type=AlertType.agent_offline, message="b", status=AlertStatus.resolved),
    ])
    db.commit()
    resp = client.get("/alerts", params={"include_resolved": "true"}, headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_alert_count(client, auth):
    db = client.app.dependency_overrides[get_db]()
    db.add_all([
        Alert(alert_type=AlertType.agent_offline, message="a", status=AlertStatus.open),
        Alert(alert_type=AlertType.agent_offline, message="b", status=AlertStatus.open),
        Alert(alert_type=AlertType.agent_offline, message="c", status=AlertStatus.resolved),
    ])
    db.commit()
    resp = client.get("/alerts/count", headers=auth)
    assert resp.json() == {"open": 2}


def test_resolve_alert(client, auth):
    db = client.app.dependency_overrides[get_db]()
    alert = Alert(alert_type=AlertType.agent_offline, message="down", status=AlertStatus.open)
    db.add(alert)
    db.commit()
    resp = client.put(f"/alerts/{alert.id}/resolve", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolved_at"] is not None


def test_resolve_alert_not_found(client, auth):
    resp = client.put("/alerts/999/resolve", headers=auth)
    assert resp.status_code == 404


def test_viewer_cannot_resolve(client, viewer_auth):
    db = client.app.dependency_overrides[get_db]()
    alert = Alert(alert_type=AlertType.agent_offline, message="down", status=AlertStatus.open)
    db.add(alert)
    db.commit()
    resp = client.put(f"/alerts/{alert.id}/resolve", headers=viewer_auth)
    assert resp.status_code == 403


def test_get_alert_rules_404_when_none(client, auth):
    db = client.app.dependency_overrides[get_db]()
    device = Device(name="d1", ip_address="10.0.0.1")
    db.add(device)
    db.commit()
    resp = client.get(f"/alert-rules/{device.id}", headers=auth)
    assert resp.status_code == 404


def test_create_alert_rules(client, auth):
    db = client.app.dependency_overrides[get_db]()
    device = Device(name="d1", ip_address="10.0.0.1")
    db.add(device)
    db.commit()
    resp = client.post(f"/alert-rules/{device.id}",
                       json={"bandwidth_in_pct": 80.0, "bandwidth_out_pct": 90.0, "enabled": True},
                       headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["bandwidth_in_pct"] == 80.0
    assert data["device_id"] == device.id


def test_update_alert_rules(client, auth):
    db = client.app.dependency_overrides[get_db]()
    device = Device(name="d1", ip_address="10.0.0.1")
    db.add(device)
    db.commit()
    client.post(f"/alert-rules/{device.id}", json={"bandwidth_in_pct": 80.0, "enabled": True}, headers=auth)
    resp = client.post(f"/alert-rules/{device.id}", json={"bandwidth_in_pct": 70.0, "enabled": True}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["bandwidth_in_pct"] == 70.0
    assert db.query(AlertRule).filter(AlertRule.device_id == device.id).count() == 1


def test_viewer_cannot_save_rules(client, viewer_auth):
    db = client.app.dependency_overrides[get_db]()
    device = Device(name="d1", ip_address="10.0.0.1")
    db.add(device)
    db.commit()
    resp = client.post(f"/alert-rules/{device.id}", json={"bandwidth_in_pct": 80.0, "enabled": True},
                       headers=viewer_auth)
    assert resp.status_code == 403


def test_alerts_require_auth(client):
    assert client.get("/alerts").status_code == 401
    assert client.get("/alerts/count").status_code == 401


def _open_alert(client):
    db = client.app.dependency_overrides[get_db]()
    alert = Alert(alert_type=AlertType.interface_down, message="down", status=AlertStatus.open)
    db.add(alert)
    db.commit()
    return db, alert


def test_acknowledge_alert(client, auth):
    _, alert = _open_alert(client)
    resp = client.put(f"/alerts/{alert.id}/acknowledge", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["acknowledged_at"] is not None
    assert data["acknowledged_by_email"] == "admin@test.com"


def test_assign_alert(client, auth):
    db, alert = _open_alert(client)
    viewer = db.query(User).filter(User.email == "viewer@test.com").first()
    resp = client.put(f"/alerts/{alert.id}/assign", json={"assigned_to": viewer.id}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["assigned_to"] == viewer.id
    assert resp.json()["assigned_to_email"] == "viewer@test.com"


def test_assign_alert_unknown_user(client, auth):
    _, alert = _open_alert(client)
    resp = client.put(f"/alerts/{alert.id}/assign", json={"assigned_to": 9999}, headers=auth)
    assert resp.status_code == 404


def test_unassign_alert(client, auth):
    db, alert = _open_alert(client)
    viewer = db.query(User).filter(User.email == "viewer@test.com").first()
    client.put(f"/alerts/{alert.id}/assign", json={"assigned_to": viewer.id}, headers=auth)
    resp = client.put(f"/alerts/{alert.id}/assign", json={"assigned_to": None}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["assigned_to"] is None


def test_set_alert_note(client, auth):
    _, alert = _open_alert(client)
    resp = client.put(f"/alerts/{alert.id}/note", json={"note": "investigating"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["note"] == "investigating"


def test_viewer_cannot_acknowledge(client, viewer_auth):
    _, alert = _open_alert(client)
    assert client.put(f"/alerts/{alert.id}/acknowledge", headers=viewer_auth).status_code == 403


def test_acknowledge_not_found(client, auth):
    assert client.put("/alerts/999/acknowledge", headers=auth).status_code == 404


def test_assignable_users_for_editor(client, auth):
    resp = client.get("/auth/users/assignable", headers=auth)
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert {"admin@test.com", "viewer@test.com"} <= emails


def test_assignable_users_requires_role(client):
    assert client.get("/auth/users/assignable").status_code == 401
