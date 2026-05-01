import uuid
from datetime import datetime, timezone


def test_register_returns_agent_id(client, auth_headers):
    resp = client.post("/register", json={"hostname": "nyc-01", "ip": "10.0.0.1"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"].startswith("nyc-01-")
    assert "devices" in data


def test_register_no_auth_returns_403(client):
    resp = client.post("/register", json={"hostname": "nyc-01", "ip": "10.0.0.1"})
    assert resp.status_code == 403


def test_register_wrong_key_returns_401(client):
    resp = client.post(
        "/register",
        json={"hostname": "nyc-01", "ip": "10.0.0.1"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401


def test_heartbeat_updates_agent(client, auth_headers):
    reg = client.post("/register", json={"hostname": "nyc-02", "ip": "10.0.0.2"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    resp = client.post("/heartbeat", json={"agent_id": agent_id, "pending_uploads": 2}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    agents = client.get("/agents", headers=auth_headers).json()
    agent = next(a for a in agents if a["agent_id"] == agent_id)
    assert agent["pending_uploads"] == 2


def test_heartbeat_unknown_agent_returns_404(client, auth_headers):
    resp = client.post("/heartbeat", json={"agent_id": "ghost", "pending_uploads": 0}, headers=auth_headers)
    assert resp.status_code == 404


def test_get_config_returns_devices(client, auth_headers, reset_db):
    reg = client.post("/register", json={"hostname": "nyc-03", "ip": "10.0.0.3"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    # Insert device directly via DB to avoid depending on Task 6's devices router
    import db
    device_id = uuid.uuid4().hex
    db.get_db().execute(
        """INSERT INTO devices
           (id, ip, hostname, snmp_version, username, auth_protocol, auth_password,
            priv_protocol, priv_password, assigned_agent_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            device_id, "192.168.1.1", None, "v3", "admin",
            "SHA256", "authpass123", "AES256", "privpass123",
            agent_id, datetime.now(timezone.utc).isoformat(),
        ],
    )
    resp = client.get(f"/config/{agent_id}", headers=auth_headers)
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) == 1
    assert devices[0]["ip"] == "192.168.1.1"


def test_get_config_unknown_agent_returns_404(client, auth_headers):
    resp = client.get("/config/ghost", headers=auth_headers)
    assert resp.status_code == 404


def test_list_agents_returns_registered(client, auth_headers):
    client.post("/register", json={"hostname": "nyc-04", "ip": "10.0.0.4"}, headers=auth_headers)
    resp = client.get("/agents", headers=auth_headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert any(a["hostname"] == "nyc-04" for a in agents)


def test_deregister_agent(client, auth_headers):
    reg = client.post("/register", json={"hostname": "nyc-05", "ip": "10.0.0.5"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    resp = client.delete(f"/agents/{agent_id}", headers=auth_headers)
    assert resp.status_code == 204
    agents = client.get("/agents", headers=auth_headers).json()
    assert not any(a["agent_id"] == agent_id for a in agents)


def test_deregister_unknown_agent_returns_404(client, auth_headers):
    resp = client.delete("/agents/ghost-id", headers=auth_headers)
    assert resp.status_code == 404
