import pytest
import time
from datetime import datetime, timezone, timedelta

def test_register_creates_agent(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    agent_id = reg.register("host-01", "10.0.0.1")
    assert agent_id.startswith("host-01-")
    assert reg.get(agent_id) is not None

def test_register_persists_to_json(tmp_path, monkeypatch, reset_registry):
    import config
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "registry.json"))
    config.settings = config.Settings()
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    reg.register("host-02", "10.0.0.2")
    assert (tmp_path / "registry.json").exists()

def test_reload_restores_agents(tmp_path, monkeypatch, reset_registry):
    import config
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "reg.json"))
    config.settings = config.Settings()
    from registry import AgentRegistry
    reg1 = AgentRegistry.__new__(AgentRegistry)
    reg1._agents = {}
    agent_id = reg1.register("host-03", "10.0.0.3")
    reg1._persist()
    reg2 = AgentRegistry.__new__(AgentRegistry)
    reg2._agents = {}
    reg2._load()
    assert reg2.get(agent_id) is not None
    assert reg2.get(agent_id).hostname == "host-03"

def test_heartbeat_updates_last_seen(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    agent_id = reg.register("host-04", "10.0.0.4")
    reg.heartbeat(agent_id, pending_uploads=3)
    assert reg.get(agent_id).last_seen is not None
    assert reg.get(agent_id).pending_uploads == 3

def test_heartbeat_unknown_agent_raises(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    with pytest.raises(KeyError):
        reg.heartbeat("nonexistent", pending_uploads=0)

def test_status_online(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    agent.last_seen = datetime.now(timezone.utc)
    assert agent.status == "online"

def test_status_degraded(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    agent.last_seen = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert agent.status == "degraded"

def test_status_offline(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    agent.last_seen = datetime.now(timezone.utc) - timedelta(seconds=360)
    assert agent.status == "offline"

def test_status_never_seen(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    assert agent.status == "offline"

def test_deregister(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    agent_id = reg.register("host-05", "10.0.0.5")
    reg.deregister(agent_id)
    assert reg.get(agent_id) is None
