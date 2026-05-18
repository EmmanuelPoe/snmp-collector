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
