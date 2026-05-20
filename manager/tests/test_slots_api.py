import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def reset_slots():
    import slots as slots_mod
    slots_mod.slot_store._slots.clear()
    yield
    slots_mod.slot_store._slots.clear()


@pytest.fixture
def client(patch_settings, reset_db, reset_registry, reset_slots):
    from main import app
    with TestClient(app) as c:
        yield c


def test_create_slot_returns_token_and_command(client, auth_headers):
    resp = client.post("/slots", json={"label": "NYC agent"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "NYC agent"
    assert len(data["token"]) == 32
    assert "CLAIM_TOKEN" in data["install_command"]
    assert data["token"] in data["install_command"]
    assert "slot_id" in data
    assert "expires_at" in data


def test_create_slot_no_auth_returns_403(client):
    resp = client.post("/slots", json={"label": "test"})
    assert resp.status_code == 403


def test_delete_slot_removes_it(client, auth_headers):
    create = client.post("/slots", json={"label": "to delete"}, headers=auth_headers)
    slot_id = create.json()["slot_id"]
    resp = client.delete(f"/slots/{slot_id}", headers=auth_headers)
    assert resp.status_code == 204


def test_delete_nonexistent_slot_returns_204(client, auth_headers):
    resp = client.delete("/slots/doesnotexist", headers=auth_headers)
    assert resp.status_code == 204


def test_claim_converts_slot_to_agent(client, auth_headers, mock_backend_empty):
    create = client.post("/slots", json={"label": "sea agent"}, headers=auth_headers)
    token = create.json()["token"]
    resp = client.post(
        "/claim",
        json={"token": token, "hostname": "sea-host-01", "ip": "10.0.0.5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "agent_id" in data
    assert "sea-agent" in data["agent_id"] or token[:8] in data["agent_id"]
    assert "devices" in data


def test_claim_invalid_token_returns_404(client, auth_headers):
    resp = client.post(
        "/claim",
        json={"token": "badtoken", "hostname": "host", "ip": "1.2.3.4"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_pending_slots_appear_in_agent_list(client, auth_headers):
    client.post("/slots", json={"label": "pending agent"}, headers=auth_headers)
    agents = client.get("/agents", headers=auth_headers).json()
    pending = [a for a in agents if a["status"] == "pending"]
    assert len(pending) == 1
    assert pending[0]["hostname"] == "pending agent"
