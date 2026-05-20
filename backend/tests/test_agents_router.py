import pytest
from auth import hash_password
from models import User, UserRole


@pytest.fixture
def viewer_headers(client, db_session):
    viewer = User(
        email="viewer@test.com",
        hashed_password=hash_password("pw"),
        role=UserRole.viewer,
        is_active=True,
        force_password_change=False,
    )
    db_session.add(viewer)
    db_session.commit()
    resp = client.post("/auth/login", data={"username": "viewer@test.com", "password": "pw"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_agents_returns_manager_response(client, admin_headers, respx_mock):
    import httpx
    respx_mock.get("http://manager:8000/internal/agents").mock(
        return_value=httpx.Response(200, json=[
            {"agent_id": "ag-01", "hostname": "nyc-01", "ip": "10.0.0.1",
             "status": "online", "last_seen": "2026-05-03T00:00:00+00:00", "pending_uploads": 0}
        ])
    )
    resp = client.get("/agents", headers=admin_headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 1
    assert agents[0]["hostname"] == "nyc-01"


def test_agents_returns_503_when_manager_down(client, admin_headers, respx_mock):
    import httpx
    respx_mock.get("http://manager:8000/internal/agents").mock(
        side_effect=httpx.ConnectError("refused")
    )
    resp = client.get("/agents", headers=admin_headers)
    assert resp.status_code == 503


def test_create_slot_proxies_to_manager(client, admin_headers, respx_mock):
    import httpx
    respx_mock.post("http://manager:8000/slots").mock(
        return_value=httpx.Response(200, json={
            "slot_id": "abc-123",
            "label": "NYC agent",
            "token": "a" * 32,
            "expires_at": "2026-05-20T12:00:00+00:00",
            "install_command": "docker run ...",
        })
    )
    resp = client.post("/agents/slots", json={"label": "NYC agent"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["slot_id"] == "abc-123"


def test_create_slot_viewer_forbidden(client, viewer_headers):
    resp = client.post("/agents/slots", json={"label": "test"}, headers=viewer_headers)
    assert resp.status_code == 403


def test_delete_slot_proxies_to_manager(client, admin_headers, respx_mock):
    import httpx
    respx_mock.delete("http://manager:8000/slots/abc-123").mock(
        return_value=httpx.Response(204)
    )
    resp = client.delete("/agents/slots/abc-123", headers=admin_headers)
    assert resp.status_code == 204


def test_create_slot_manager_down_returns_503(client, admin_headers, respx_mock):
    import httpx
    respx_mock.post("http://manager:8000/slots").mock(side_effect=httpx.RequestError("down"))
    resp = client.post("/agents/slots", json={"label": "test"}, headers=admin_headers)
    assert resp.status_code == 503


def test_delete_slot_manager_down_returns_503(client, admin_headers, respx_mock):
    import httpx
    respx_mock.delete("http://manager:8000/slots/abc").mock(side_effect=httpx.RequestError("down"))
    resp = client.delete("/agents/slots/abc", headers=admin_headers)
    assert resp.status_code == 503
