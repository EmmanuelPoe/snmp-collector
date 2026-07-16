"""Per-agent credential handling (Step 1.7): secret persisted 0600 next to the
agent-id file; requests use `Bearer <agent_id>:<secret>`, falling back to the
shared key only when no secret is stored (pre-1.7 enrollments)."""
import os
import stat
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

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


def test_save_secret_mode_0600_and_roundtrip(agent_env):
    import credentials
    credentials.save_secret("s3cret-token")
    path = agent_env / "agent_secret"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert credentials.load_secret() == "s3cret-token"


def test_load_secret_missing_returns_none(agent_env):
    import credentials
    assert credentials.load_secret() is None


def test_auth_token_prefers_agent_secret(agent_env):
    import credentials
    assert credentials.auth_token("ag-01", "s3cret") == "ag-01:s3cret"


def test_auth_token_falls_back_to_shared_key(agent_env):
    import credentials
    assert credentials.auth_token("ag-01", None) == "shared-key"
    assert credentials.auth_token(None, None) == "shared-key"
