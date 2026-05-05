import pytest

def test_schema_creates_all_tables(reset_db):
    import db
    conn = db.get_db()
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    assert "snmp_polls" in tables
    assert "snmp_traps" in tables
    assert "ingest_log" in tables

@pytest.mark.asyncio
async def test_query_returns_rows(reset_db):
    import db
    conn = db.get_db()
    conn.execute(
        "INSERT INTO snmp_polls (agent_id, device_ip, oid, collected_at) VALUES ('agent-01','1.2.3.4','1.3.6.1.2.1.1.3.0',current_timestamp)"
    )
    rows = await db.query("SELECT agent_id FROM snmp_polls WHERE agent_id = ?", ["agent-01"])
    assert len(rows) == 1
    assert rows[0][0] == "agent-01"

@pytest.mark.asyncio
async def test_execute_write(reset_db):
    import db
    await db.execute(
        "INSERT INTO snmp_polls (agent_id, device_ip, oid, collected_at) VALUES (?,?,?,current_timestamp)",
        ["agent-02", "1.2.3.5", "1.3.6.1.2.1.1.3.0"]
    )
    rows = await db.query("SELECT agent_id FROM snmp_polls WHERE agent_id = ?", ["agent-02"])
    assert rows[0][0] == "agent-02"

@pytest.mark.asyncio
async def test_ingest_parquet_polls(reset_db, sample_polls_parquet):
    import db
    count = await db.ingest_parquet("snmp_polls", str(sample_polls_parquet))
    assert count == 5
    rows = await db.query("SELECT COUNT(*) FROM snmp_polls")
    assert rows[0][0] == 5

@pytest.mark.asyncio
async def test_ingest_parquet_traps(reset_db, sample_traps_parquet):
    import db
    count = await db.ingest_parquet("snmp_traps", str(sample_traps_parquet))
    assert count == 3

@pytest.mark.asyncio
async def test_close_and_reopen(reset_db, tmp_path, monkeypatch):
    import db, config
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    config.settings = config.Settings()
    db._conn = None
    conn1 = db.get_db()
    conn1.execute("INSERT INTO snmp_polls (agent_id, device_ip, oid, collected_at) VALUES ('agent-03','1.2.3.6','1.3.6.1.2.1.1.3.0',current_timestamp)")
    db.close_db()
    conn2 = db.get_db()
    rows = await db.query("SELECT agent_id FROM snmp_polls WHERE agent_id = ?", ["agent-03"])
    assert rows[0][0] == "agent-03"


def test_snmp_polls_has_interface_name_and_oid_name_columns(reset_db):
    import db
    conn = db.get_db()
    cols = {row[0] for row in conn.execute("DESCRIBE snmp_polls").fetchall()}
    assert "interface_name" in cols
    assert "oid_name" in cols

def test_devices_table_does_not_exist(reset_db):
    import db
    conn = db.get_db()
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert "devices" not in tables
