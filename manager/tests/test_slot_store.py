import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture(autouse=True)
def patch_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_API_KEY", "test-key")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setenv("SLOTS_PATH", str(tmp_path / "slots.json"))
    monkeypatch.setenv("DEAD_LETTER_PATH", str(tmp_path / "dead-letter"))
    monkeypatch.setenv("BACKEND_URL", "http://backend-mock:8000")
    import config
    config.settings = config.Settings()


@pytest.fixture
def store(tmp_path):
    import config
    config.settings.slots_path = str(tmp_path / "slots.json")
    from slots import SlotStore
    return SlotStore()


def test_create_returns_slot_with_token(store):
    slot = store.create("NYC agent")
    assert slot.label == "NYC agent"
    assert len(slot.token) == 32
    assert slot.status == "pending"


def test_get_by_token_finds_slot(store):
    slot = store.create("LAX agent")
    found = store.get_by_token(slot.token)
    assert found is not None
    assert found.slot_id == slot.slot_id


def test_get_by_token_returns_none_for_unknown(store):
    assert store.get_by_token("notatoken") is None


def test_claim_removes_slot_and_returns_agent_id(store):
    slot = store.create("SEA agent")
    agent_id = store.claim(slot.token, "sea-host-01", "10.0.0.5")
    assert "sea-agent" in agent_id or slot.token[:8] in agent_id
    assert store.get_by_token(slot.token) is None


def test_claim_unknown_token_raises(store):
    with pytest.raises(KeyError):
        store.claim("badtoken", "host", "1.2.3.4")


def test_expired_slots_are_purged(store):
    slot = store.create("expiring")
    store._slots[slot.slot_id].expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    store._persist()
    from slots import SlotStore
    fresh = SlotStore()
    assert len(fresh.all()) == 0


def test_delete_removes_slot(store):
    slot = store.create("deletable")
    store.delete(slot.slot_id)
    assert store.get_by_token(slot.token) is None


def test_all_excludes_expired(store):
    slot = store.create("stale")
    store._slots[slot.slot_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert len(store.all()) == 0


def test_persistence_survives_reload(store, tmp_path):
    slot = store.create("persisted")
    from slots import SlotStore
    reloaded = SlotStore()
    assert reloaded.get_by_token(slot.token) is not None
