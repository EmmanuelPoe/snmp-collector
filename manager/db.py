import duckdb
import asyncio
from pathlib import Path
from config import settings

_conn: duckdb.DuckDBPyConnection | None = None
_write_lock = asyncio.Lock()

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS snmp_polls (
        agent_id     VARCHAR NOT NULL,
        device_ip    VARCHAR NOT NULL,
        oid          VARCHAR NOT NULL,
        value        VARCHAR,
        collected_at TIMESTAMPTZ NOT NULL
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
    """CREATE TABLE IF NOT EXISTS devices (
        id                VARCHAR PRIMARY KEY,
        ip                VARCHAR NOT NULL,
        hostname          VARCHAR,
        snmp_version      VARCHAR DEFAULT 'v3',
        username          VARCHAR NOT NULL,
        auth_protocol     VARCHAR NOT NULL,
        auth_password     VARCHAR NOT NULL,
        priv_protocol     VARCHAR NOT NULL,
        priv_password     VARCHAR NOT NULL,
        assigned_agent_id VARCHAR,
        created_at        TIMESTAMPTZ NOT NULL,
        last_polled_at    TIMESTAMPTZ
    )""",
]


def get_db() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        _conn = duckdb.connect(settings.db_path)
        for stmt in _SCHEMA:
            _conn.execute(stmt)
    return _conn


def close_db() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def query(sql: str, params: list | None = None) -> list[tuple]:
    conn = get_db()
    if params:
        return conn.execute(sql, params).fetchall()
    return conn.execute(sql).fetchall()


async def execute(sql: str, params: list | None = None) -> None:
    async with _write_lock:
        conn = get_db()
        if params:
            conn.execute(sql, params)
        else:
            conn.execute(sql)


async def ingest_parquet(table: str, file_path: str) -> int:
    """Bulk load parquet file into table. Returns number of rows inserted."""
    async with _write_lock:
        conn = get_db()
        before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.execute(f"INSERT INTO {table} SELECT * FROM read_parquet($1)", [file_path])
        after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return after - before
