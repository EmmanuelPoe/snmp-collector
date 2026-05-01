import pytest

def test_schema_creates_all_tables(reset_db):
    import db
    conn = db.get_db()
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    assert "snmp_polls" in tables
    assert "snmp_traps" in tables
    assert "ingest_log" in tables
    assert "devices" in tables

def test_query_returns_rows(reset_db):
    import db
    conn = db.get_db()
    conn.execute(
        "INSERT INTO devices VALUES ('id1','1.2.3.4',NULL,'v3','user','SHA256',"
        "'authpass','AES256','privpass',NULL,current_timestamp,NULL)"
    )
    rows = db.query("SELECT id FROM devices WHERE id = ?", ["id1"])
    assert len(rows) == 1
    assert rows[0][0] == "id1"

@pytest.mark.asyncio
async def test_execute_write(reset_db):
    import db
    await db.execute(
        "INSERT INTO devices VALUES (?,?,NULL,'v3',?,?,?,?,?,NULL,current_timestamp,NULL)",
        ["id2", "1.2.3.5", "user", "SHA256", "auth", "AES256", "priv"]
    )
    rows = db.query("SELECT id FROM devices WHERE id = ?", ["id2"])
    assert rows[0][0] == "id2"

@pytest.mark.asyncio
async def test_ingest_parquet_polls(reset_db, sample_polls_parquet):
    import db
    count = await db.ingest_parquet("snmp_polls", str(sample_polls_parquet))
    assert count == 5
    rows = db.query("SELECT COUNT(*) FROM snmp_polls")
    assert rows[0][0] == 5

@pytest.mark.asyncio
async def test_ingest_parquet_traps(reset_db, sample_traps_parquet):
    import db
    count = await db.ingest_parquet("snmp_traps", str(sample_traps_parquet))
    assert count == 3

def test_close_and_reopen(reset_db, tmp_path, monkeypatch):
    import db, config
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    config.settings = config.Settings()
    db._conn = None
    conn1 = db.get_db()
    conn1.execute("INSERT INTO devices VALUES ('id3','1.2.3.6',NULL,'v3','u','SHA256','a','AES256','p',NULL,current_timestamp,NULL)")
    db.close_db()
    conn2 = db.get_db()
    rows = db.query("SELECT id FROM devices WHERE id = ?", ["id3"])
    assert rows[0][0] == "id3"
