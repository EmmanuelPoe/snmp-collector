import pytest


@pytest.fixture(autouse=True)
def _clear_commands():
    import commands
    commands.command_store._commands.clear()
    yield
    commands.command_store._commands.clear()


def test_enqueue_and_fetch_once(client, auth_headers):
    r = client.post("/agents/agent-1/commands",
                    json={"type": "walk", "params": {"base_oid": "1.3.6.1.2.1"}},
                    headers=auth_headers)
    assert r.status_code == 200
    cid = r.json()["command_id"]

    pending = client.get("/agents/agent-1/commands", headers=auth_headers).json()
    assert len(pending) == 1
    assert pending[0]["command_id"] == cid
    assert pending[0]["type"] == "walk"

    # second poll: already dispatched, not returned again
    assert client.get("/agents/agent-1/commands", headers=auth_headers).json() == []


def test_fetch_is_scoped_to_agent(client, auth_headers):
    client.post("/agents/agent-1/commands", json={"type": "walk", "params": {}}, headers=auth_headers)
    assert client.get("/agents/agent-2/commands", headers=auth_headers).json() == []


def test_result_and_get(client, auth_headers):
    cid = client.post("/agents/a/commands", json={"type": "walk", "params": {}},
                      headers=auth_headers).json()["command_id"]
    client.get("/agents/a/commands", headers=auth_headers)  # dispatch
    r = client.post(f"/commands/{cid}/result",
                    json={"status": "done", "result": [{"oid": "1.3.6.1.2.1.1.1.0", "value": "sysDescr"}]},
                    headers=auth_headers)
    assert r.status_code == 200
    got = client.get(f"/commands/{cid}", headers=auth_headers).json()
    assert got["status"] == "done"
    assert got["result"][0]["oid"] == "1.3.6.1.2.1.1.1.0"


def test_result_unknown_command_404(client, auth_headers):
    assert client.post("/commands/nope/result", json={"status": "done"},
                       headers=auth_headers).status_code == 404


def test_get_unknown_command_404(client, auth_headers):
    assert client.get("/commands/nope", headers=auth_headers).status_code == 404


def test_commands_require_auth(client):
    assert client.get("/agents/a/commands").status_code == 403
    assert client.post("/agents/a/commands", json={"type": "walk", "params": {}}).status_code == 403
