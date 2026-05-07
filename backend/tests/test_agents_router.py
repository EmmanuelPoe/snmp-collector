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
