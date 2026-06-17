"""Tests for notification channels (router CRUD + dispatch service)."""
from auth import hash_password
from database import get_db
from models import (
    Alert, AlertSeverity, AlertStatus, AlertType,
    NotificationChannel, User, UserRole,
)
from services import notifications as notif_service


# --- router ---

def test_list_channels_empty(client, admin_headers):
    r = client.get("/notification-channels", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_channel_defaults_severity_filter(client, admin_headers):
    r = client.post("/notification-channels",
                    json={"name": "ops", "type": "slack", "url": "https://hooks.slack.com/x"},
                    headers=admin_headers)
    assert r.status_code == 201
    d = r.json()
    assert d["type"] == "slack"
    assert d["severity_filter"] == ["critical", "warning", "info"]
    assert d["enabled"] is True


def test_create_channel_invalid_type_rejected(client, admin_headers):
    r = client.post("/notification-channels",
                    json={"name": "x", "type": "pagerduty", "url": "http://x"},
                    headers=admin_headers)
    assert r.status_code == 422


def test_update_channel(client, admin_headers):
    cid = client.post("/notification-channels",
                      json={"name": "ops", "type": "webhook", "url": "http://x"},
                      headers=admin_headers).json()["id"]
    r = client.put(f"/notification-channels/{cid}",
                   json={"enabled": False, "severity_filter": ["critical"]},
                   headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["severity_filter"] == ["critical"]


def test_delete_channel(client, admin_headers):
    cid = client.post("/notification-channels",
                      json={"name": "ops", "type": "webhook", "url": "http://x"},
                      headers=admin_headers).json()["id"]
    assert client.delete(f"/notification-channels/{cid}", headers=admin_headers).status_code == 204
    assert client.get("/notification-channels", headers=admin_headers).json() == []


def test_channels_require_auth(client):
    assert client.get("/notification-channels").status_code == 401


def test_viewer_cannot_create_channel(client, db_session):
    db_session.add(User(email="v@test.com", hashed_password=hash_password("pw"),
                        role=UserRole.viewer, is_active=True, force_password_change=False))
    db_session.commit()
    token = client.post("/auth/login", data={"username": "v@test.com", "password": "pw"}).json()["access_token"]
    r = client.post("/notification-channels",
                    json={"name": "x", "type": "slack", "url": "http://x"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


# --- dispatch service ---

def _alert(db, alert_type, severity, message="m", device_id=None):
    a = Alert(alert_type=alert_type, severity=severity, message=message,
              status=AlertStatus.open, device_id=device_id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_dispatch_filters_by_severity(db_session, monkeypatch):
    db_session.add(NotificationChannel(name="crit-only", type="slack", url="http://s",
                                       severity_filter=["critical"], enabled=True))
    db_session.commit()
    sent = []
    monkeypatch.setattr(notif_service.httpx, "post", lambda url, **k: sent.append(url))

    notif_service.dispatch_alert(db_session, _alert(db_session, AlertType.interface_down, AlertSeverity.warning))
    assert sent == []  # warning filtered out

    notif_service.dispatch_alert(db_session, _alert(db_session, AlertType.device_unreachable, AlertSeverity.critical))
    assert sent == ["http://s"]


def test_dispatch_empty_filter_matches_all(db_session, monkeypatch):
    db_session.add(NotificationChannel(name="all", type="webhook", url="http://w",
                                       severity_filter=[], enabled=True))
    db_session.commit()
    sent = []
    monkeypatch.setattr(notif_service.httpx, "post", lambda url, **k: sent.append(url))
    notif_service.dispatch_alert(db_session, _alert(db_session, AlertType.error_rate, AlertSeverity.info))
    assert sent == ["http://w"]


def test_dispatch_disabled_channel_skipped(db_session, monkeypatch):
    db_session.add(NotificationChannel(name="off", type="webhook", url="http://w",
                                       severity_filter=[], enabled=False))
    db_session.commit()
    sent = []
    monkeypatch.setattr(notif_service.httpx, "post", lambda url, **k: sent.append(url))
    notif_service.dispatch_alert(db_session, _alert(db_session, AlertType.agent_offline, AlertSeverity.critical))
    assert sent == []


def test_dispatch_swallows_channel_errors(db_session, monkeypatch):
    db_session.add(NotificationChannel(name="bad", type="webhook", url="http://w",
                                       severity_filter=[], enabled=True))
    db_session.commit()

    def boom(*a, **k):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(notif_service.httpx, "post", boom)
    # Must not raise
    notif_service.dispatch_alert(db_session, _alert(db_session, AlertType.agent_offline, AlertSeverity.critical))


def test_dispatch_payload_shapes(db_session, monkeypatch):
    db_session.add(NotificationChannel(name="s", type="slack", url="http://slack",
                                       severity_filter=[], enabled=True))
    db_session.add(NotificationChannel(name="w", type="webhook", url="http://wh",
                                       severity_filter=[], enabled=True))
    db_session.commit()
    calls = {}
    monkeypatch.setattr(notif_service.httpx, "post",
                        lambda url, json=None, **k: calls.__setitem__(url, json))
    notif_service.dispatch_alert(
        db_session,
        _alert(db_session, AlertType.interface_down, AlertSeverity.warning, "eth0 down", device_id=5))
    assert "text" in calls["http://slack"]
    assert calls["http://wh"]["message"] == "eth0 down"
    assert calls["http://wh"]["severity"] == "warning"
    assert calls["http://wh"]["device_id"] == 5
