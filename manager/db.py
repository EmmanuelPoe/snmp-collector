import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import duckdb

logger = logging.getLogger(__name__)

_conn: duckdb.DuckDBPyConnection | None = None
_write_lock = asyncio.Lock()
# Step 2.3 backpressure: how many coroutines are holding or waiting on the
# write lock. /ingest sheds load (503 + Retry-After) above INGEST_MAX_QUEUE.
_waiters = 0


def write_queue_depth() -> int:
    return _waiters


@asynccontextmanager
async def _locked():
    global _waiters
    _waiters += 1
    try:
        async with _write_lock:
            yield
    finally:
        _waiters -= 1


_ALLOWED_TABLES = frozenset({"snmp_polls", "snmp_traps"})

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS snmp_polls (
        agent_id       VARCHAR NOT NULL,
        device_ip      VARCHAR NOT NULL,
        interface_name VARCHAR,
        oid_name       VARCHAR,
        oid            VARCHAR NOT NULL,
        value          VARCHAR,
        collected_at   TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS snmp_traps (
        agent_id     VARCHAR NOT NULL,
        device_ip    VARCHAR NOT NULL,
        trap_oid     VARCHAR NOT NULL,
        varbinds     VARCHAR,
        received_at  TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ingest_log (
        file_id      VARCHAR PRIMARY KEY,
        ingested_at  TIMESTAMPTZ NOT NULL,
        row_count    INTEGER NOT NULL
    )""",
]


def _migrate(conn: duckdb.DuckDBPyConnection) -> None:
    """Add new columns to snmp_polls for existing databases. Only the
    table-missing case is expected (fresh DB — _SCHEMA creates it right after);
    anything else is real corruption and must abort startup, not be swallowed
    (Step 2.2)."""
    try:
        cols = {row[0] for row in conn.execute("DESCRIBE snmp_polls").fetchall()}
    except duckdb.CatalogException:
        return  # fresh database — _SCHEMA will create the table
    except Exception as exc:
        logger.error("DuckDB schema inspection failed (%s): %s", config.settings.db_path, exc)
        raise
    if "interface_name" not in cols:
        conn.execute("ALTER TABLE snmp_polls ADD COLUMN interface_name VARCHAR")
    if "oid_name" not in cols:
        conn.execute("ALTER TABLE snmp_polls ADD COLUMN oid_name VARCHAR")


def get_db() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        Path(config.settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        _conn = duckdb.connect(config.settings.db_path)
        _migrate(_conn)
        for stmt in _SCHEMA:
            _conn.execute(stmt)
    return _conn


def close_db() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None


async def query(sql: str, params: list | None = None) -> list[tuple]:
    async with _locked():
        conn = get_db()
        if params is not None:
            return conn.execute(sql, params).fetchall()
        return conn.execute(sql).fetchall()


async def execute(sql: str, params: list | None = None) -> None:
    async with _locked():
        conn = get_db()
        if params is not None:
            conn.execute(sql, params)
        else:
            conn.execute(sql)


async def backup_database(dest_dir: str) -> dict:
    """Safe copy of the live DuckDB file (Step 2.4): CHECKPOINT then copy,
    all inside the write lock so no writer touches the file mid-copy. Ingest
    requests arriving meanwhile are absorbed by Step 2.3 backpressure."""
    import shutil

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = Path(dest_dir) / f"metrics-{ts}.db"
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with _locked():
        conn = get_db()
        conn.execute("CHECKPOINT")
        shutil.copy2(config.settings.db_path, dest)
    return {"path": str(dest), "bytes": dest.stat().st_size}


async def purge_old_metrics(retention_days: int) -> dict:
    """Delete polls/traps older than retention_days. Delete-only: DuckDB reuses
    the freed space for subsequent inserts, so the file stabilises at steady
    state rather than growing unboundedly."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    async with _locked():
        conn = get_db()
        polls = conn.execute("SELECT COUNT(*) FROM snmp_polls WHERE collected_at < ?", [cutoff]).fetchone()[0]
        traps = conn.execute("SELECT COUNT(*) FROM snmp_traps WHERE received_at < ?", [cutoff]).fetchone()[0]
        conn.execute("DELETE FROM snmp_polls WHERE collected_at < ?", [cutoff])
        conn.execute("DELETE FROM snmp_traps WHERE received_at < ?", [cutoff])
    return {"polls_deleted": polls, "traps_deleted": traps}


async def ingest_parquet(table: str, file_path: str) -> int:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table!r}")
    async with _locked():
        conn = get_db()
        before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if table == "snmp_polls":
            conn.execute(
                "INSERT INTO snmp_polls (agent_id, device_ip, interface_name, oid_name, oid, value, collected_at) "
                "SELECT agent_id, device_ip, interface_name, oid_name, oid, value, collected_at "
                "FROM read_parquet($1)",
                [file_path],
            )
        else:
            conn.execute(f"INSERT INTO {table} SELECT * FROM read_parquet($1)", [file_path])
        after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return after - before


async def transactional_ingest(table: str, file_path: str, file_id: str, ingested_at, row_count: int) -> None:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table!r}")
    async with _locked():
        conn = get_db()
        conn.execute("BEGIN")
        try:
            if table == "snmp_polls":
                conn.execute(
                    "INSERT INTO snmp_polls (agent_id, device_ip, interface_name, oid_name, oid, value, collected_at) "
                    "SELECT agent_id, device_ip, interface_name, oid_name, oid, value, collected_at "
                    "FROM read_parquet($1)",
                    [file_path],
                )
            else:
                conn.execute(f"INSERT INTO {table} SELECT * FROM read_parquet($1)", [file_path])
            conn.execute(
                "INSERT INTO ingest_log VALUES (?, ?, ?)",
                [file_id, ingested_at, row_count],
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
