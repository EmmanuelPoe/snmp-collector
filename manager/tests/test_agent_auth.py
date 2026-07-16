"""Per-agent credentials (Step 1.7 / plan Step 19): agents authenticate with
`Bearer <agent_id>:<secret>`; the shared key survives on agent routes only in
grace mode (AGENT_AUTH_ENFORCE=false)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def two_agents(client, auth_headers, mock_backend_empty):
    """Register agents A and B via the API; returns their (agent_id, cred_headers)."""
    agents = []
    for host in ("host-a", "host-b"):
        resp = client.post("/register", json={"hostname": host, "ip": "10.0.0.1"},
                           headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_secret"]
        cred = {"Authorization": f"Bearer {data['agent_id']}:{data['agent_secret']}"}
        agents.append((data["agent_id"], cred))
    return agents


def test_register_and_claim_return_secret_once(client, auth_headers, mock_backend_empty):
    resp = client.post("/register", json={"hostname": "h", "ip": "1.2.3.4"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["agent_secret"]

    # Only the hash is stored in the registry.
    from registry import registry
    info = registry.get(resp.json()["agent_id"])
    assert info.secret_hash
    assert info.secret_hash != resp.json()["agent_secret"]

    slot = client.post("/slots", json={"label": "edge-1"}, headers=auth_headers).json()
    claim = client.post("/claim", json={"token": slot["token"], "hostname": "edge", "ip": "5.6.7.8"})
    assert claim.status_code == 200
    assert claim.json()["agent_secret"]


def test_agent_credential_works_on_own_routes(client, two_agents, mock_backend_empty):
    (agent_a, cred_a), _ = two_agents
    assert client.post("/heartbeat", json={"agent_id": agent_a}, headers=cred_a).status_code == 200
    assert client.get(f"/config/{agent_a}", headers=cred_a).status_code == 200
    assert client.get(f"/agents/{agent_a}/commands", headers=cred_a).status_code == 200


def test_agent_cannot_act_as_other_agent(client, two_agents):
    (agent_a, _), (_, cred_b) = two_agents
    assert client.post("/heartbeat", json={"agent_id": agent_a}, headers=cred_b).status_code == 403
    assert client.get(f"/config/{agent_a}", headers=cred_b).status_code == 403
    assert client.get(f"/agents/{agent_a}/commands", headers=cred_b).status_code == 403


def test_command_result_only_from_target_agent(client, two_agents, auth_headers):
    (agent_a, cred_a), (_, cred_b) = two_agents
    cid = client.post(f"/agents/{agent_a}/commands",
                      json={"type": "walk", "params": {}},
                      headers=auth_headers).json()["command_id"]
    resp = client.post(f"/commands/{cid}/result", json={"status": "done", "result": []},
                       headers=cred_b)
    assert resp.status_code == 403
    resp = client.post(f"/commands/{cid}/result", json={"status": "done", "result": []},
                       headers=cred_a)
    assert resp.status_code == 200


def test_bad_secret_rejected(client, two_agents):
    (agent_a, _), _ = two_agents
    bad = {"Authorization": f"Bearer {agent_a}:wrong-secret"}
    assert client.post("/heartbeat", json={"agent_id": agent_a}, headers=bad).status_code == 401


def test_deregister_kills_credential(client, two_agents, auth_headers):
    (agent_a, cred_a), _ = two_agents
    assert client.delete(f"/agents/{agent_a}", headers=auth_headers).status_code == 204
    assert client.post("/heartbeat", json={"agent_id": agent_a}, headers=cred_a).status_code == 401


def test_shared_key_accepted_on_agent_routes_in_grace_mode(client, two_agents, auth_headers):
    (agent_a, _), _ = two_agents
    resp = client.post("/heartbeat", json={"agent_id": agent_a}, headers=auth_headers)
    assert resp.status_code == 200


def test_enforce_rejects_shared_key_on_agent_routes(client, two_agents, auth_headers,
                                                    mock_backend_empty, monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "agent_auth_enforce", True)
    (agent_a, cred_a), _ = two_agents
    # Shared key dead on agent routes...
    assert client.post("/heartbeat", json={"agent_id": agent_a}, headers=auth_headers).status_code == 401
    assert client.get(f"/config/{agent_a}", headers=auth_headers).status_code == 401
    assert client.get(f"/agents/{agent_a}/commands", headers=auth_headers).status_code == 401
    # ...per-agent credential still works...
    assert client.post("/heartbeat", json={"agent_id": agent_a}, headers=cred_a).status_code == 200
    # ...and operator routes keep using the shared key.
    assert client.get("/agents", headers=auth_headers).status_code == 200
    assert client.post("/register", json={"hostname": "h2", "ip": "9.9.9.9"},
                       headers=auth_headers).status_code == 200


def test_ingest_requires_agent_credential_under_enforce(client, two_agents, auth_headers,
                                                        sample_polls_parquet, monkeypatch,
                                                        reset_db):
    import config
    monkeypatch.setattr(config.settings, "agent_auth_enforce", True)
    (_, cred_a), _ = two_agents
    import hashlib
    sha = hashlib.sha256(sample_polls_parquet.read_bytes()).hexdigest()

    def _post(headers):
        with open(sample_polls_parquet, "rb") as f:
            return client.post(
                "/ingest",
                files={"file": ("polls.parquet", f, "application/octet-stream")},
                headers={**headers, "X-File-ID": "abc123_polls", "X-SHA256": sha},
            )

    assert _post(auth_headers).status_code == 401
    resp = _post(cred_a)
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 5


def test_secret_hash_survives_registry_reload(client, auth_headers, mock_backend_empty):
    resp = client.post("/register", json={"hostname": "h", "ip": "1.2.3.4"}, headers=auth_headers)
    agent_id, secret = resp.json()["agent_id"], resp.json()["agent_secret"]
    import registry as reg_mod
    reloaded = reg_mod.AgentRegistry()
    assert reloaded.get(agent_id).verify_secret(secret)
