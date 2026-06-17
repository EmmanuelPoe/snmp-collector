import pytest
from datetime import datetime, timezone, timedelta


def _insert_poll(conn, collected_at):
    conn.execute(
        "INSERT INTO snmp_polls (agent_id, device_ip, oid, value, collected_at) "
        "VALUES ('a1','1.2.3.4','1.3.6',  '1', ?)",
        [collected_at],
    )


def _insert_trap(conn, received_at):
    conn.execute(
        "INSERT INTO snmp_traps (agent_id, device_ip, trap_oid, varbinds, received_at) "
        "VALUES ('a1','1.2.3.4','1.3.6.1','{}', ?)",
        [received_at],
    )


@pytest.mark.asyncio
async def test_purge_deletes_old_keeps_recent(reset_db):
    import db
    conn = db.get_db()
    now = datetime.now(timezone.utc)
    _insert_poll(conn, now - timedelta(days=120))   # old
    _insert_poll(conn, now - timedelta(days=10))     # recent
    _insert_trap(conn, now - timedelta(days=200))    # old
    _insert_trap(conn, now - timedelta(days=1))      # recent

    result = await db.purge_old_metrics(90)

    assert result == {"polls_deleted": 1, "traps_deleted": 1}
    polls = conn.execute("SELECT COUNT(*) FROM snmp_polls").fetchone()[0]
    traps = conn.execute("SELECT COUNT(*) FROM snmp_traps").fetchone()[0]
    assert polls == 1
    assert traps == 1


@pytest.mark.asyncio
async def test_purge_noop_when_all_recent(reset_db):
    import db
    conn = db.get_db()
    now = datetime.now(timezone.utc)
    _insert_poll(conn, now - timedelta(days=5))
    result = await db.purge_old_metrics(90)
    assert result == {"polls_deleted": 0, "traps_deleted": 0}
    assert conn.execute("SELECT COUNT(*) FROM snmp_polls").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_purge_respects_retention_days(reset_db):
    import db
    conn = db.get_db()
    now = datetime.now(timezone.utc)
    _insert_poll(conn, now - timedelta(days=15))
    # 15-day-old row: kept at 90d retention, deleted at 7d retention
    assert (await db.purge_old_metrics(90))["polls_deleted"] == 0
    assert (await db.purge_old_metrics(7))["polls_deleted"] == 1
