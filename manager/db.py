import duckdb
import asyncio
from pathlib import Path
import config

_conn: duckdb.DuckDBPyConnection | None = None
_write_lock = asyncio.Lock()
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
    """Add new columns to snmp_polls for existing databases."""
    try:
        cols = {row[0] for row in conn.execute("DESCRIBE snmp_polls").fetchall()}
        if "interface_name" not in cols:
            conn.execute("ALTER TABLE snmp_polls ADD COLUMN interface_name VARCHAR")
        if "oid_name" not in cols:
            conn.execute("ALTER TABLE snmp_polls ADD COLUMN oid_name VARCHAR")
    except Exception:
        pass  # Table may not exist yet — _SCHEMA will create it


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
    async with _write_lock:
        conn = get_db()
        if params is not None:
            return conn.execute(sql, params).fetchall()
        return conn.execute(sql).fetchall()


async def execute(sql: str, params: list | None = None) -> None:
    async with _write_lock:
        conn = get_db()
        if params is not None:
            conn.execute(sql, params)
        else:
            conn.execute(sql)


async def ingest_parquet(table: str, file_path: str) -> int:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table!r}")
    async with _write_lock:
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
    async with _write_lock:
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
