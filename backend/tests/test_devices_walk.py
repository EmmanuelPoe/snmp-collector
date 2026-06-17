"""Tests for the MIB-browser walk proxy endpoints."""
import httpx
import pytest

from models import Device


@pytest.fixture
def device(db_session):
    d = Device(name="sw", ip_address="10.0.0.1", snmp_version="2c",
               snmp_community="public", assigned_agent_id="agent-1")
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return d


def test_walk_enqueues_on_assigned_agent(client, admin_headers, device, respx_mock):
    route = respx_mock.post("http://manager:8000/agents/agent-1/commands").mock(
        return_value=httpx.Response(200, json={"command_id": "cmd-123"}))
    resp = client.post(f"/devices/{device.id}/walk", params={"base_oid": "1.3.6.1.2.1"},
                       headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["command_id"] == "cmd-123"
    # the enqueued command carries device creds + base_oid
    sent = route.calls.last.request
    import json
    body = json.loads(sent.content)
    assert body["type"] == "walk"
    assert body["params"]["device"]["ip"] == "10.0.0.1"
    assert body["params"]["base_oid"] == "1.3.6.1.2.1"


def test_walk_unknown_device_404(client, admin_headers):
    assert client.post("/devices/9999/walk", headers=admin_headers).status_code == 404


def test_walk_no_agent_returns_503(client, admin_headers, db_session, respx_mock):
    d = Device(name="noagent", ip_address="10.0.0.2", snmp_version="2c", snmp_community="public")
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    # no assigned agent -> backend asks manager for an online one; none available
    respx_mock.get("http://manager:8000/agents").mock(return_value=httpx.Response(200, json=[]))
    resp = client.post(f"/devices/{d.id}/walk", headers=admin_headers)
    assert resp.status_code == 503


def test_walk_falls_back_to_online_agent(client, admin_headers, db_session, respx_mock):
    d = Device(name="noagent2", ip_address="10.0.0.3", snmp_version="2c", snmp_community="public")
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    respx_mock.get("http://manager:8000/agents").mock(return_value=httpx.Response(
        200, json=[{"agent_id": "agent-x", "status": "online"}]))
    route = respx_mock.post("http://manager:8000/agents/agent-x/commands").mock(
        return_value=httpx.Response(200, json={"command_id": "cmd-9"}))
    resp = client.post(f"/devices/{d.id}/walk", headers=admin_headers)
    assert resp.status_code == 200
    assert route.called


def test_get_walk_result_proxied(client, admin_headers, respx_mock):
    respx_mock.get("http://manager:8000/commands/cmd-123").mock(return_value=httpx.Response(
        200, json={"command_id": "cmd-123", "status": "done",
                   "result": [{"oid": "1.3.6.1.2.1.1.1.0", "value": "sysDescr"}], "error": None}))
    resp = client.get("/devices/walk/cmd-123", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert resp.json()["result"][0]["value"] == "sysDescr"


def test_walk_requires_editor(client, db_session, device):
    from auth import hash_password
    from models import User, UserRole
    db_session.add(User(email="v@test.com", hashed_password=hash_password("pw"),
                        role=UserRole.viewer, is_active=True, force_password_change=False))
    db_session.commit()
    token = client.post("/auth/login", data={"username": "v@test.com", "password": "pw"}).json()["access_token"]
    resp = client.post(f"/devices/{device.id}/walk", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
