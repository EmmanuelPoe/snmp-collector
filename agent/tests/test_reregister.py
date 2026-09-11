"""Self-heal on manager 404 (Step 2.1 follow-up): if the manager's registry was
reset/migrated/restored and no longer knows this agent, a 404 on heartbeat or
config triggers a fresh registration that re-points the upload buffers at the
new id+token — instead of looping on 404 forever."""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# main.py imports snmp + trap_receiver, which require pysnmp (not installed for
# unit tests). Stub them so `import main` works without the SNMP stack.
_snmp = types.ModuleType("snmp")
_snmp.walk_device = _snmp.walk_lldp = _snmp.walk_oid = lambda *a, **k: []
sys.modules.setdefault("snmp", _snmp)
_trap = types.ModuleType("trap_receiver")


async def _run_trap_listener(*a, **k):
    return None


_trap.run_trap_listener = _run_trap_listener
sys.modules.setdefault("trap_receiver", _trap)

import pytest


@pytest.fixture
def agent_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_URL", "http://manager:8000")
    monkeypatch.setenv("MANAGER_API_KEY", "shared-key")
    monkeypatch.setenv("QUEUE_PATH", str(tmp_path / "queue"))
    monkeypatch.setenv("AGENT_ID_PATH", str(tmp_path / "agent_id"))
    monkeypatch.setenv("AGENT_SECRET_PATH", str(tmp_path / "agent_secret"))
    import config

    config.settings = config.Settings()
    return tmp_path


@pytest.mark.asyncio
async def test_reregister_swaps_identity_and_repoints_buffers(agent_env, monkeypatch):
    import credentials
    import main
    from uploader import UploadBuffer

    # Enrolled state: stored id + secret, buffer pointing at the old identity.
    Path(agent_env / "agent_id").write_text("old-id")
    credentials.save_secret("old-secret")
    main._agent_id, main._agent_secret = "old-id", "old-secret"
    main._buffer = UploadBuffer(agent_id="old-id", token="old-id:old-secret")
    main._trap_buffer = None

    async def fake_register():
        # A real _register would POST /register or /claim; here just hand back a
        # fresh identity as the manager would.
        Path(agent_env / "agent_id").write_text("new-id")
        credentials.save_secret("new-secret")
        return "new-id", "new-secret"

    monkeypatch.setattr(main, "_register", fake_register)

    await main._reregister("old-id")

    assert main._agent_id == "new-id"
    assert main._agent_secret == "new-secret"
    # Buffer now authenticates as the new agent.
    assert main._buffer._agent_id == "new-id"
    assert main._buffer._token == "new-id:new-secret"


@pytest.mark.asyncio
async def test_reregister_is_idempotent_under_concurrent_callers(agent_env, monkeypatch):
    import main
    from uploader import UploadBuffer

    main._agent_id, main._agent_secret = "already-new", "s"
    main._buffer = UploadBuffer(agent_id="already-new", token="already-new:s")
    main._trap_buffer = None

    calls = {"n": 0}

    async def fake_register():
        calls["n"] += 1
        return "should-not-run", None

    monkeypatch.setattr(main, "_register", fake_register)

    # A second loop calls with a stale id that has already been superseded.
    await main._reregister("old-id")

    assert calls["n"] == 0  # guard skips the redundant re-registration
    assert main._agent_id == "already-new"
