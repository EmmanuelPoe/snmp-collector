"""Postgres registry backend (Step 2.1 / plan Step 25), exercised against a
SQLite URL — SQLAlchemy Core only, so the logic is identical; CI's e2e stack
covers the real-Postgres path."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_db_registry(tmp_path):
    from registry import DbAgentRegistry

    url = f"sqlite:///{tmp_path}/registry.db"
    # Stand in for Alembic migration 025: create the table, then start fresh.
    bootstrap = DbAgentRegistry(database_url=url)
    bootstrap._table.create(bootstrap._engine, checkfirst=True)
    return DbAgentRegistry(database_url=url), url


def test_register_upserts_row_and_reload_restores(tmp_path):
    from registry import DbAgentRegistry

    reg, url = _make_db_registry(tmp_path)
    agent_id, secret = reg.register("host-db", "10.1.1.1")

    reloaded = DbAgentRegistry(database_url=url)
    info = reloaded.get(agent_id)
    assert info is not None
    assert info.hostname == "host-db"
    assert info.verify_secret(secret)
    assert info.last_seen is not None


def test_heartbeat_updates_persisted_row(tmp_path):
    from registry import DbAgentRegistry

    reg, url = _make_db_registry(tmp_path)
    agent_id, _ = reg.register("host-db", "10.1.1.1")
    reg.heartbeat(agent_id, pending_uploads=5)

    reloaded = DbAgentRegistry(database_url=url)
    assert reloaded.get(agent_id).pending_uploads == 5


def test_deregister_deletes_row(tmp_path):
    from registry import DbAgentRegistry

    reg, url = _make_db_registry(tmp_path)
    agent_id, _ = reg.register("host-db", "10.1.1.1")
    reg.deregister(agent_id)

    reloaded = DbAgentRegistry(database_url=url)
    assert reloaded.get(agent_id) is None


def test_add_via_claim_path_persists_secret_hash(tmp_path):
    from registry import AgentInfo, DbAgentRegistry, hash_secret, new_secret

    reg, url = _make_db_registry(tmp_path)
    secret = new_secret()
    info = AgentInfo("edge-1-abc", "edge-1", "10.2.2.2", secret_hash=hash_secret(secret))
    info.last_seen = datetime.now(timezone.utc)
    reg.add(info)

    reloaded = DbAgentRegistry(database_url=url)
    assert reloaded.get("edge-1-abc").verify_secret(secret)


def test_unreachable_db_degrades_to_empty_not_crash(tmp_path, caplog):
    from registry import DbAgentRegistry

    # Nonexistent directory -> connection failures on load and save.
    reg = DbAgentRegistry(database_url=f"sqlite:///{tmp_path}/missing-dir/nope/x.db")
    assert reg.all() == []
    # Writes fail with a warning, not an exception; memory stays authoritative.
    agent_id, _ = reg.register("host-db", "10.1.1.1")
    assert reg.get(agent_id) is not None
