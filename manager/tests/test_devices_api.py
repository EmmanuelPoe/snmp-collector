import pytest

DEVICE_PAYLOAD = {
    "ip": "10.1.1.1",
    "hostname": "sw-core-01",
    "username": "snmpv3user",
    "auth_protocol": "SHA256",
    "auth_password": "authpassword1",
    "priv_protocol": "AES256",
    "priv_password": "privpassword1",
}

def test_add_device_returns_201(client, auth_headers):
    resp = client.post("/devices", json=DEVICE_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["ip"] == "10.1.1.1"
    assert data["hostname"] == "sw-core-01"
    assert "id" in data
    assert "auth_password" not in data  # passwords not returned in response

def test_list_devices_returns_added(client, auth_headers):
    client.post("/devices", json=DEVICE_PAYLOAD, headers=auth_headers)
    resp = client.get("/devices", headers=auth_headers)
    assert resp.status_code == 200
    devices = resp.json()
    assert any(d["ip"] == "10.1.1.1" for d in devices)

def test_delete_device(client, auth_headers):
    add_resp = client.post("/devices", json=DEVICE_PAYLOAD, headers=auth_headers)
    device_id = add_resp.json()["id"]
    del_resp = client.delete(f"/devices/{device_id}", headers=auth_headers)
    assert del_resp.status_code == 204
    list_resp = client.get("/devices", headers=auth_headers)
    assert not any(d["id"] == device_id for d in list_resp.json())

def test_delete_nonexistent_returns_404(client, auth_headers):
    resp = client.delete("/devices/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404

def test_add_device_with_agent_assignment(client, auth_headers):
    reg = client.post("/register", json={"hostname": "ag-01", "ip": "10.0.0.1"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    payload = {**DEVICE_PAYLOAD, "assigned_agent_id": agent_id}
    resp = client.post("/devices", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["assigned_agent_id"] == agent_id

def test_config_only_returns_assigned_devices(client, auth_headers):
    reg = client.post("/register", json={"hostname": "ag-02", "ip": "10.0.0.2"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    # Device assigned to this agent
    client.post("/devices", json={**DEVICE_PAYLOAD, "ip": "10.1.1.2", "assigned_agent_id": agent_id}, headers=auth_headers)
    # Unassigned device
    client.post("/devices", json={**DEVICE_PAYLOAD, "ip": "10.1.1.3"}, headers=auth_headers)
    resp = client.get(f"/config/{agent_id}", headers=auth_headers)
    ips = [d["ip"] for d in resp.json()]
    assert "10.1.1.2" in ips
    assert "10.1.1.3" not in ips

def test_devices_no_auth_returns_403(client):
    resp = client.get("/devices")
    assert resp.status_code == 403
