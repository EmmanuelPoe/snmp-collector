import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone

@pytest.fixture(autouse=True)
def patch_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_API_KEY", "test-key")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setenv("DEAD_LETTER_PATH", str(tmp_path / "dead-letter"))
    # Force settings reload
    import config
    config.settings = config.Settings()

@pytest.fixture
def reset_db():
    import db
    db._conn = None
    yield
    if db._conn:
        db._conn.close()
        db._conn = None

@pytest.fixture
def reset_registry():
    import registry as reg_mod
    reg_mod.registry._agents.clear()

@pytest.fixture
def client(patch_settings, reset_db, reset_registry):
    from main import app
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-key"}

@pytest.fixture
def sample_polls_parquet(tmp_path):
    rows = 5
    table = pa.table({
        "agent_id": pa.array(["agent-01"] * rows),
        "device_ip": pa.array(["192.168.1.1"] * rows),
        "oid": pa.array(["1.3.6.1.2.1.1.3.0"] * rows),
        "value": pa.array(["12345"] * rows),
        "collected_at": pa.array([datetime.now(timezone.utc)] * rows, type=pa.timestamp("us", tz="UTC")),
    })
    path = tmp_path / "polls.parquet"
    pq.write_table(table, path)
    return path

@pytest.fixture
def sample_traps_parquet(tmp_path):
    rows = 3
    table = pa.table({
        "agent_id": pa.array(["agent-01"] * rows),
        "device_ip": pa.array(["192.168.1.1"] * rows),
        "trap_oid": pa.array(["1.3.6.1.6.3.1.1.5.3"] * rows),
        "varbinds": pa.array(['{"ifIndex": "1"}'] * rows),
        "received_at": pa.array([datetime.now(timezone.utc)] * rows, type=pa.timestamp("us", tz="UTC")),
    })
    path = tmp_path / "traps.parquet"
    pq.write_table(table, path)
    return path
