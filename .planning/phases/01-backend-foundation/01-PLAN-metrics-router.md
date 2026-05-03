---
phase: 1
plan: 1.3
title: "Rewrite metrics router to read DuckDB"
wave: 2
depends_on: [1.1]
autonomous: true
files_modified:
  - backend/routers/metrics.py
  - backend/schemas.py
requirements:
  - BE-04
must_haves:
  goal: "GET /metrics queries DuckDB parquet data, not Postgres; joins device_ip to device_id via Postgres"
  truths:
    - "GET /metrics?device_id=1 returns metric rows sourced from DuckDB, not snmp_metrics or if_mib_metrics tables"
    - "GET /metrics opens DuckDB at /data/db/metrics.db in read-only mode using duckdb.connect(read_only=True)"
    - "DuckDB query joins device ip_address from Postgres devices table to match device_id filter"
    - "MetricResponse shape is preserved: id, device_id, timestamp, interface_name, oid_name, value fields returned"
    - "GET /metrics/available/{device_id} returns interface and oid_name data sourced from DuckDB"
    - "No import of SNMPMetric or IfMibMetric remains in routers/metrics.py"
---

<objective>
Rewrite `backend/routers/metrics.py` to read from DuckDB (`/data/db/metrics.db`) instead of Postgres. The DuckDB file is the `snmp_polls` table written by the manager (parquet pre-parsed with `interface_name` and `oid_name` columns). Device IP-to-ID resolution uses a Postgres query via the existing SQLAlchemy session.

Purpose: Postgres metrics tables are dropped in Plan 1.1. Metrics now live in the manager's DuckDB file, mounted read-only into the backend container. The metrics router must be the sole consumer of that data.

Output:
- `backend/routers/metrics.py` — fully rewritten, DuckDB-backed
- `backend/schemas.py` — no schema changes required (MetricResponse shape is preserved); may need to add `module` query param to MetricQuery if not present
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<interfaces>
<!-- DuckDB file path: /data/db/metrics.db (from docker-compose.yml manager DB_PATH=/data/db/metrics.db) -->
<!-- DuckDB table: snmp_polls — columns include at minimum: -->
<!--   timestamp (TIMESTAMPTZ or similar), device_ip (VARCHAR), interface_name (VARCHAR), -->
<!--   oid_name (VARCHAR), value (DOUBLE or FLOAT) -->
<!-- Parquet pre-parsed: interface_name and oid_name are stored as string columns (no OID translation needed) -->
<!-- DuckDB connection: duckdb.connect('/data/db/metrics.db', read_only=True) -->
<!-- DuckDB Python package: already installed (manager uses it; backend requirements must include it) -->

<!-- Postgres Device table (after Plan 1.1): id (Integer), ip_address (String), name (String) -->
<!-- Join strategy: query Postgres for device.ip_address WHERE device.id = device_id param -->
<!--   then use ip_address as filter in DuckDB query -->

<!-- Existing MetricResponse schema (schemas.py): -->
<!--   id: int, device_id: int, timestamp: datetime, interface_name: Optional[str], -->
<!--   interface_index: Optional[int], oid: str, oid_name: Optional[str], value: Optional[float], -->
<!--   value_type: Optional[str] -->

<!-- DuckDB rows do not have an `id` column — synthesize with row_number() or enumerate in Python -->
<!-- DuckDB rows do not have device_id — inject from the query parameter -->
<!-- DuckDB rows do not have interface_index — set to None -->
<!-- DuckDB rows do not have value_type — set to "gauge" -->
<!-- oid field in MetricResponse: set equal to oid_name (DuckDB stores name, not numeric OID) -->

<!-- /metrics/collect/{device_id} POST endpoint: REMOVE (collector is gone) -->
<!-- /metrics/stats/{device_id}/{interface_name} GET: REWRITE to use DuckDB -->
<!-- /metrics/latest/{device_id} GET: REWRITE to use DuckDB -->
<!-- /metrics/available/{device_id} GET: REWRITE to use DuckDB -->
<!-- /metrics/interfaces/{device_id} GET: keep as stub returning [] or rewrite with DuckDB -->
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Rewrite metrics.py with DuckDB backend</name>
  <files>backend/routers/metrics.py</files>
  <read_first>
    - backend/routers/metrics.py — read the full existing file to understand all route signatures and response shapes that must be preserved or explicitly removed
    - backend/schemas.py — confirm MetricResponse field names before writing return dicts
    - backend/database.py — confirm get_db signature (needed for Postgres device lookup)
    - backend/models.py — confirm Device class has id and ip_address columns (after Plan 1.1 edits)
  </read_first>
  <action>
Replace the entire content of `backend/routers/metrics.py` with the following implementation.

Key design decisions:
- DuckDB opened per-request with `duckdb.connect('/data/db/metrics.db', read_only=True)` then closed in a `finally` block — no connection pooling needed for read-only analytics queries
- Device IP lookup via Postgres (existing `get_db` dependency) translates `device_id` → `ip_address`
- If DuckDB file does not exist yet (manager not running), return empty list rather than 500
- Remove `POST /metrics/collect/{device_id}` entirely (collector is gone)
- Preserve route paths: `GET /metrics`, `GET /metrics/available/{device_id}`, `GET /metrics/latest/{device_id}`, `GET /metrics/interfaces/{device_id}`, `GET /metrics/stats/{device_id}/{interface_name}`

```python
import duckdb
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from database import get_db
from models import Device
from schemas import MetricResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])

DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "/data/db/metrics.db")


def _open_duckdb() -> Optional[duckdb.DuckDBPyConnection]:
    """Open DuckDB read-only. Returns None if file does not exist."""
    if not os.path.exists(DUCKDB_PATH):
        logger.warning(f"DuckDB file not found at {DUCKDB_PATH} — returning empty results")
        return None
    return duckdb.connect(DUCKDB_PATH, read_only=True)


def _device_ip(device_id: int, db: Session) -> Optional[str]:
    """Look up device IP address from Postgres by device_id."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        return None
    return device.ip_address


def _rows_to_metrics(rows, device_id: int) -> List[dict]:
    """Convert DuckDB result rows to MetricResponse-compatible dicts.

    Expected row columns: timestamp, interface_name, oid_name, value
    Synthesized: id (enumerate), device_id (param), interface_index=None, oid=oid_name, value_type='gauge'
    """
    results = []
    for i, row in enumerate(rows):
        results.append({
            "id": i + 1,
            "device_id": device_id,
            "timestamp": row[0],
            "interface_name": row[1],
            "interface_index": None,
            "oid": row[2],       # oid_name used as oid identifier
            "oid_name": row[2],
            "value": float(row[3]) if row[3] is not None else None,
            "value_type": "gauge",
        })
    return results


@router.get("", response_model=List[MetricResponse])
def query_metrics(
    device_id: Optional[int] = None,
    interface_name: Optional[str] = None,
    oid: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """Query metrics from DuckDB snmp_polls table."""
    conn = _open_duckdb()
    if conn is None:
        return []

    try:
        conditions = []
        params = []

        if device_id is not None:
            ip = _device_ip(device_id, db)
            if ip is None:
                raise HTTPException(status_code=404, detail="Device not found")
            conditions.append("device_ip = ?")
            params.append(ip)

        if interface_name is not None:
            conditions.append("interface_name = ?")
            params.append(interface_name)

        if oid is not None:
            conditions.append("oid_name = ?")
            params.append(oid)

        if start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(start_time)

        if end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT timestamp, interface_name, oid_name, value
            FROM snmp_polls
            {where}
            ORDER BY timestamp DESC
            LIMIT {int(limit)}
        """
        rows = conn.execute(sql, params).fetchall()
        result_device_id = device_id if device_id is not None else 0
        return _rows_to_metrics(rows, result_device_id)
    finally:
        conn.close()


@router.get("/available/{device_id}")
def get_available_metrics(device_id: int, db: Session = Depends(get_db)):
    """Return available interfaces and oid_names for a device from DuckDB."""
    ip = _device_ip(device_id, db)
    if ip is None:
        raise HTTPException(status_code=404, detail="Device not found")

    conn = _open_duckdb()
    if conn is None:
        return {"modules": {}}

    try:
        interfaces = conn.execute(
            "SELECT DISTINCT interface_name FROM snmp_polls WHERE device_ip = ? AND interface_name IS NOT NULL",
            [ip]
        ).fetchall()
        oid_names = conn.execute(
            "SELECT DISTINCT oid_name FROM snmp_polls WHERE device_ip = ? AND oid_name IS NOT NULL",
            [ip]
        ).fetchall()

        return {
            "modules": {
                "snmp_polls": {
                    "metrics": sorted([r[0] for r in oid_names if r[0]]),
                    "interfaces": sorted([r[0] for r in interfaces if r[0]]),
                }
            }
        }
    finally:
        conn.close()


@router.get("/latest/{device_id}", response_model=List[MetricResponse])
def get_latest_metrics(device_id: int, limit: int = 100, db: Session = Depends(get_db)):
    """Return the most recent metric rows for a device."""
    ip = _device_ip(device_id, db)
    if ip is None:
        raise HTTPException(status_code=404, detail="Device not found")

    conn = _open_duckdb()
    if conn is None:
        return []

    try:
        rows = conn.execute(
            "SELECT timestamp, interface_name, oid_name, value FROM snmp_polls WHERE device_ip = ? ORDER BY timestamp DESC LIMIT ?",
            [ip, limit]
        ).fetchall()
        return _rows_to_metrics(rows, device_id)
    finally:
        conn.close()


@router.get("/interfaces/{device_id}")
def get_device_interfaces(device_id: int, db: Session = Depends(get_db)):
    """Return distinct interfaces for a device."""
    ip = _device_ip(device_id, db)
    if ip is None:
        raise HTTPException(status_code=404, detail="Device not found")

    conn = _open_duckdb()
    if conn is None:
        return []

    try:
        rows = conn.execute(
            "SELECT DISTINCT interface_name FROM snmp_polls WHERE device_ip = ? AND interface_name IS NOT NULL",
            [ip]
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    finally:
        conn.close()


@router.get("/stats/{device_id}/{interface_name}")
def get_interface_stats(
    device_id: int,
    interface_name: str,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Return time-series metrics for a specific device interface."""
    ip = _device_ip(device_id, db)
    if ip is None:
        raise HTTPException(status_code=404, detail="Device not found")

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    conn = _open_duckdb()
    if conn is None:
        return {"device_id": device_id, "interface_name": interface_name,
                "time_range": {"start": start_time, "end": end_time, "hours": hours},
                "metrics": []}

    try:
        rows = conn.execute(
            """SELECT timestamp, interface_name, oid_name, value
               FROM snmp_polls
               WHERE device_ip = ? AND interface_name = ? AND timestamp >= ? AND timestamp <= ?
               ORDER BY timestamp""",
            [ip, interface_name, start_time, end_time]
        ).fetchall()
        flat = _rows_to_metrics(rows, device_id)
        return {
            "device_id": device_id,
            "interface_name": interface_name,
            "time_range": {"start": start_time, "end": end_time, "hours": hours},
            "metrics": flat,
        }
    finally:
        conn.close()
```

Also add `DUCKDB_PATH` to `backend/config.py` Settings:
```python
duckdb_path: str = "/data/db/metrics.db"
```
And change the constant in metrics.py to use settings:
```python
from config import settings
DUCKDB_PATH = settings.duckdb_path
```

Note: `duckdb` must be in the backend's requirements. Check `backend/requirements.txt` — if `duckdb` is not listed, add it. The manager already uses duckdb so the package is present in the repo ecosystem; the backend just needs it in its own requirements file.
  </action>
  <verify>
    <automated>python -c "
import ast
src = open('backend/routers/metrics.py').read()
ast.parse(src)
assert 'duckdb.connect' in src, 'missing duckdb.connect'
assert 'SNMPMetric' not in src, 'SNMPMetric still referenced'
assert 'IfMibMetric' not in src, 'IfMibMetric still referenced'
assert 'collect_device_metrics' not in src, 'collector still referenced'
assert 'snmp_polls' in src, 'missing snmp_polls table reference'
assert '/internal' not in src, 'wrong prefix'
print('metrics.py checks passed')
"</automated>
  </verify>
  <done>
    - `backend/routers/metrics.py` contains `duckdb.connect` call with `read_only=True`
    - `backend/routers/metrics.py` has no import of `SNMPMetric`, `IfMibMetric`, or `collect_device_metrics`
    - `backend/routers/metrics.py` queries table `snmp_polls` in all DuckDB SQL
    - `GET /metrics`, `GET /metrics/available/{device_id}`, `GET /metrics/latest/{device_id}`, `GET /metrics/interfaces/{device_id}`, `GET /metrics/stats/{device_id}/{interface_name}` all exist
    - `POST /metrics/collect/{device_id}` does NOT exist
    - `backend/requirements.txt` contains `duckdb`
    - File parses without syntax errors
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DuckDB file → backend | Read-only file mount; backend cannot write to metrics.db |
| frontend → GET /metrics | Query parameters from untrusted frontend reach DuckDB SQL |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1.3-01 | Tampering | DuckDB file mount | mitigate | Volume mounted `:ro` in docker-compose (BE-08); DuckDB connection opened with `read_only=True` as second layer |
| T-1.3-02 | Injection | DuckDB SQL query params | mitigate | All user-supplied values (device_id, interface_name, oid, times) passed as `?` positional parameters — DuckDB parameterized query prevents injection |
| T-1.3-03 | Denial of Service | Unbounded LIMIT from frontend | mitigate | `limit` param defaults to 1000; `int(limit)` cast prevents string injection; add `Query(default=1000, le=10000)` annotation |
</threat_model>

<verification>
```bash
# Syntax check
python -c "import ast; ast.parse(open('backend/routers/metrics.py').read()); print('syntax ok')"

# No stale Postgres metrics references
grep -v 'SNMPMetric\|IfMibMetric\|collect_device_metrics' backend/routers/metrics.py | grep -c 'import' || true

# DuckDB referenced correctly
grep -c 'duckdb.connect' backend/routers/metrics.py
grep -c 'read_only=True' backend/routers/metrics.py
grep -c 'snmp_polls' backend/routers/metrics.py

# collect endpoint removed
grep -c 'collect' backend/routers/metrics.py | grep '^0$' || echo "WARNING: collect still present"

# duckdb in requirements
grep -i 'duckdb' backend/requirements.txt
```
</verification>

<success_criteria>
- `routers/metrics.py` uses `duckdb.connect(path, read_only=True)` for all metric queries
- All SQL queries target `snmp_polls` table with parameterized `?` placeholders
- `_device_ip()` helper resolves device_id → ip_address via Postgres before querying DuckDB
- No reference to `SNMPMetric`, `IfMibMetric`, or `collect_device_metrics` in metrics.py
- `duckdb` present in `backend/requirements.txt`
- All five GET routes preserved with same URL paths as before
</success_criteria>

<output>
After completion, create `.planning/phases/01-backend-foundation/01-1.3-SUMMARY.md`
</output>
