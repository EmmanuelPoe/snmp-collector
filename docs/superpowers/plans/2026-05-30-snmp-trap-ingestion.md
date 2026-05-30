# SNMP Trap Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SNMP trap reception to the agent. When a trap arrives on UDP 162, the agent parses it, buffers it, and uploads it to the manager as a Parquet file (using the existing `*_traps` ingest path). The backend exposes a `/traps` query endpoint. The frontend shows a Traps page with a live table.

**Architecture:** The agent grows a `_trap_loop()` that listens on UDP 162 using `pysnmp`'s async trap receiver. Traps are buffered in a separate `TrapBuffer` (same flush/upload pattern as `UploadBuffer` but writes `snmp_traps` schema Parquet with `_traps` file suffix). The manager already handles `*_traps` ingest end-to-end. The backend adds `GET /traps` querying DuckDB read-only. The frontend adds a Traps page.

**Tech Stack:** Python asyncio, pysnmp (already in agent), pyarrow, FastAPI, React, Recharts

**Key constraint:** Trap listening is opt-in via `TRAP_ENABLED=true` env var. When disabled, the loop never starts and no UDP port is opened.

---

## File Map

| Action | File |
|--------|------|
| Modify | `agent/config.py` |
| Create | `agent/trap_receiver.py` |
| Modify | `agent/uploader.py` |
| Modify | `agent/main.py` |
| Modify | `agent/requirements.txt` |
| Modify | `docker-compose.yml` |
| Modify | `manager/routers/metrics.py` |
| Modify | `backend/routers/metrics.py` |
| Modify | `frontend/src/services/api.js` |
| Create | `frontend/src/components/TrapsPage.js` |
| Modify | `frontend/src/components/Sidebar.js` |
| Modify | `frontend/src/App.js` (or router file) |

---

### Task 1: Agent config and trap buffer

**Files:**
- Modify: `agent/config.py`
- Modify: `agent/uploader.py`

- [ ] **Step 1: Add trap settings to `agent/config.py`**

Add after `agent_id_path`:

```python
trap_enabled: bool = False
trap_listen_port: int = 162
trap_community: str = "public"
```

- [ ] **Step 2: Add `TrapBuffer` to `agent/uploader.py`**

`TrapBuffer` uses the same upload infrastructure as `UploadBuffer` but writes the `snmp_traps` schema and uses `_traps` file suffix. Add after the existing `UploadBuffer` class:

```python
class TrapBuffer:
    def __init__(self, agent_id: str):
        self._agent_id = agent_id
        self._rows: list[dict] = []
        self._queue = Path(config.settings.queue_path) / "traps"
        self._queue.mkdir(parents=True, exist_ok=True)

    async def add(self, row: dict) -> None:
        self._rows.append(row)
        if len(self._rows) >= 50:
            await self._flush()

    async def flush(self) -> None:
        await self._flush()

    async def _flush(self) -> None:
        if not self._rows:
            return
        rows, self._rows = self._rows, []
        file_id = f"{uuid.uuid4().hex}_traps"
        path = self._queue / f"{file_id}.parquet"
        _write_traps_parquet(rows, path)
        await self._upload_file(path, file_id)

    async def _upload_file(self, path: Path, file_id: str) -> None:
        sha256 = _sha256(path)
        try:
            async with httpx.AsyncClient() as client:
                with open(path, "rb") as f:
                    resp = await client.post(
                        f"{config.settings.manager_url}/ingest",
                        files={"file": (path.name, f, "application/octet-stream")},
                        headers={
                            "Authorization": f"Bearer {config.settings.manager_api_key}",
                            "X-File-ID": file_id,
                            "X-SHA256": sha256,
                        },
                        timeout=30.0,
                    )
                    resp.raise_for_status()
            path.unlink(missing_ok=True)
        except Exception as exc:
            log.warning("Trap upload failed: %s", exc)
```

Add the Parquet writer (uses `snmp_traps` schema — matches `manager/db.py`):

```python
def _write_traps_parquet(rows: list[dict], path: Path) -> None:
    table = pa.table({
        "agent_id":    pa.array([r["agent_id"] for r in rows]),
        "device_ip":   pa.array([r["device_ip"] for r in rows]),
        "trap_oid":    pa.array([r["trap_oid"] for r in rows]),
        "varbinds":    pa.array([r["varbinds"] for r in rows]),
        "received_at": pa.array(
            [datetime.fromisoformat(r["received_at"]) for r in rows],
            type=pa.timestamp("us", tz="UTC"),
        ),
    })
    pq.write_table(table, path)
```

Note: `TrapBuffer` needs `import logging` at the top — add `log = logging.getLogger(__name__)` if not present.

- [ ] **Step 3: Commit**

```bash
git add agent/config.py agent/uploader.py
git commit -m "feat: add trap_enabled config and TrapBuffer for trap Parquet upload"
```

---

### Task 2: Trap receiver

**Files:**
- Create: `agent/trap_receiver.py`

The trap receiver uses `pysnmp`'s `AsyncioUdpTransport` to listen on UDP 162 and parse incoming trap PDUs. Each trap is converted to a row dict and passed to `TrapBuffer`.

- [ ] **Step 1: Check pysnmp is available in agent requirements**

```bash
grep pysnmp agent/requirements.txt
```

If missing, add `pysnmp>=6.0` to `agent/requirements.txt`.

- [ ] **Step 2: Create `agent/trap_receiver.py`**

```python
import json
import logging
from datetime import datetime, timezone

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config as snmp_config, engine
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.hlapi.asyncio import SnmpEngine

import config as agent_config

log = logging.getLogger(__name__)


def build_trap_listener(agent_id: str, trap_buffer) -> SnmpEngine:
    """
    Returns a configured SnmpEngine that listens for traps and feeds TrapBuffer.
    Call snmpEngine.transportDispatcher.runDispatcher() to start (blocking),
    or use run_trap_listener() for the asyncio-friendly wrapper.
    """
    snmp_engine = SnmpEngine()

    snmp_config.addTransport(
        snmp_engine,
        udp.domainName,
        udp.UdpTransport().openServerMode(("0.0.0.0", agent_config.settings.trap_listen_port)),
    )

    snmp_config.addV1System(
        snmp_engine,
        "trap-community",
        agent_config.settings.trap_community,
    )

    def _trap_callback(snmp_engine, state_reference, context_engine_id,
                       context_name, var_binds, cb_ctx):
        now = datetime.now(timezone.utc).isoformat()
        trap_oid = None
        varbinds = {}
        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val)
            if trap_oid is None:
                trap_oid = oid_str
            varbinds[oid_str] = val_str

        source_ip = cb_ctx.get("transportAddress", ("unknown",))[0] if isinstance(cb_ctx, dict) else "unknown"

        row = {
            "agent_id": agent_id,
            "device_ip": source_ip,
            "trap_oid": trap_oid or "unknown",
            "varbinds": json.dumps(varbinds),
            "received_at": now,
        }
        import asyncio
        asyncio.get_event_loop().create_task(trap_buffer.add(row))
        log.info("Trap received from %s oid=%s", source_ip, trap_oid)

    ntfrcv.NotificationReceiver(snmp_engine, _trap_callback)
    return snmp_engine


async def run_trap_listener(agent_id: str, trap_buffer) -> None:
    """Asyncio-compatible trap listener. Runs until cancelled."""
    import asyncio
    snmp_engine = build_trap_listener(agent_id, trap_buffer)
    snmp_engine.transportDispatcher.jobStarted(1)
    log.info(
        "Trap listener started on UDP port %d (community: %s)",
        agent_config.settings.trap_listen_port,
        agent_config.settings.trap_community,
    )
    try:
        while True:
            snmp_engine.transportDispatcher.runDispatcher(0.1)
            await asyncio.sleep(0)
    except asyncio.CancelledError:
        snmp_engine.transportDispatcher.closeDispatcher()
        log.info("Trap listener stopped")
```

- [ ] **Step 3: Commit**

```bash
git add agent/trap_receiver.py agent/requirements.txt
git commit -m "feat: add pysnmp-based trap receiver"
```

---

### Task 3: Wire trap loop into agent main

**Files:**
- Modify: `agent/main.py`

- [ ] **Step 1: Add `_trap_loop()` and `TrapBuffer` to `agent/main.py`**

Add import at the top:
```python
from uploader import UploadBuffer, TrapBuffer
from trap_receiver import run_trap_listener
```

Add module-level global after `_buffer`:
```python
_trap_buffer: TrapBuffer | None = None
```

Add the trap loop function after `_retry_loop`:
```python
async def _trap_loop() -> None:
    await run_trap_listener(_agent_id, _trap_buffer)
```

Add a periodic flush for the trap buffer (every 30s) inside `_retry_loop`:
```python
async def _retry_loop() -> None:
    while True:
        await asyncio.sleep(60)
        await _buffer.flush_retry_queue()
        await _buffer.tick()
        if _trap_buffer:
            await _trap_buffer.flush()
```

- [ ] **Step 2: Initialise `TrapBuffer` and conditionally start `_trap_loop` in `main()`**

Replace the existing `main()`:

```python
async def main() -> None:
    global _agent_id, _buffer, _trap_buffer
    _agent_id = await _register()
    _buffer = UploadBuffer(agent_id=_agent_id)

    loops = [
        _heartbeat_loop(),
        _poll_loop(),
        _retry_loop(),
    ]

    if config.settings.trap_enabled:
        _trap_buffer = TrapBuffer(agent_id=_agent_id)
        loops.append(_trap_loop())
        log.info("Trap ingestion enabled on port %d", config.settings.trap_listen_port)

    await asyncio.gather(*loops)
```

- [ ] **Step 3: Add `TRAP_ENABLED` and `TRAP_LISTEN_PORT` to `docker-compose.yml`**

In the `agent` service `environment` block, add:
```yaml
- TRAP_ENABLED=${TRAP_ENABLED:-false}
- TRAP_LISTEN_PORT=${TRAP_LISTEN_PORT:-162}
- TRAP_COMMUNITY=${TRAP_COMMUNITY:-public}
```

Add a conditional port mapping in the `agent` service:
```yaml
ports:
  - "${TRAP_LISTEN_PORT:-162}:162/udp"
```

Add to `.env.example`:
```bash
# SNMP Trap ingestion (agent)
TRAP_ENABLED=false
TRAP_LISTEN_PORT=162
TRAP_COMMUNITY=public
```

- [ ] **Step 4: Build agent and verify it starts with trap disabled**

```bash
docker-compose build agent && docker-compose up -d agent
docker-compose logs agent --tail=20
```

Expected: agent starts normally with no trap-related log lines.

- [ ] **Step 5: Commit**

```bash
git add agent/main.py docker-compose.yml .env.example
git commit -m "feat: wire trap loop into agent — opt-in via TRAP_ENABLED=true"
```

---

### Task 4: Manager — traps query endpoint

**Files:**
- Modify: `manager/routers/metrics.py`

The manager already ingests traps into `snmp_traps`. It just needs a read endpoint.

- [ ] **Step 1: Add `GET /internal/traps` to `manager/routers/metrics.py`**

Add after the existing `/history` endpoint:

```python
@router.get("/traps")
async def query_traps(
    device_ip: Optional[str] = None,
    trap_oid: Optional[str] = None,
    hours: float = Query(default=24.0, gt=0, le=720),
    limit: int = Query(default=200, le=1000),
    _: str = Depends(require_api_key),
):
    cutoff = _dt.now(timezone.utc) - timedelta(hours=hours)
    conditions = ["received_at >= ?"]
    params: list = [cutoff]
    if device_ip:
        conditions.append("device_ip = ?")
        params.append(device_ip)
    if trap_oid:
        conditions.append("trap_oid LIKE ?")
        params.append(f"%{trap_oid}%")
    params.append(limit)

    rows = await query(
        f"SELECT agent_id, device_ip, trap_oid, varbinds, received_at "
        f"FROM snmp_traps WHERE {' AND '.join(conditions)} "
        f"ORDER BY received_at DESC LIMIT ?",
        params,
    )
    return [
        {
            "agent_id": r[0],
            "device_ip": r[1],
            "trap_oid": r[2],
            "varbinds": r[3],
            "received_at": r[4],
        }
        for r in rows
    ]
```

Note: the router prefix is `/internal/metrics` so the full path is `/internal/metrics/traps`.

- [ ] **Step 2: Restart manager and verify endpoint**

```bash
docker-compose restart manager
curl -s "http://localhost:8001/internal/metrics/traps?hours=24&limit=5" \
  -H "Authorization: Bearer change-me-in-production" | python3 -m json.tool
```

Expected: `[]` (no traps yet) without error.

- [ ] **Step 3: Commit**

```bash
git add manager/routers/metrics.py
git commit -m "feat: add GET /internal/metrics/traps query endpoint"
```

---

### Task 5: Backend proxy for traps

**Files:**
- Modify: `backend/routers/metrics.py`

- [ ] **Step 1: Add `GET /metrics/traps` to `backend/routers/metrics.py`**

Add after the `/history` endpoint:

```python
@router.get("/traps")
def get_traps(
    device_id: Optional[int] = None,
    trap_oid: Optional[str] = None,
    hours: float = 24.0,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    params: dict = {"hours": hours, "limit": limit}
    if device_id:
        device_ip = _device_ip(device_id, db)
        params["device_ip"] = device_ip
    if trap_oid:
        params["trap_oid"] = trap_oid
    return _manager_get("/traps", params)
```

- [ ] **Step 2: Rebuild backend and verify**

```bash
docker-compose build backend && docker-compose up -d backend
sleep 5
curl -s "http://localhost/api/metrics/traps" \
  -H "Authorization: Bearer <jwt>" | python3 -m json.tool
```

Expected: `[]`.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/metrics.py
git commit -m "feat: proxy GET /metrics/traps through backend"
```

---

### Task 6: Frontend — Traps page

**Files:**
- Modify: `frontend/src/services/api.js`
- Create: `frontend/src/components/TrapsPage.js`
- Modify: `frontend/src/components/Sidebar.js`
- Modify: `frontend/src/App.js` (or wherever routes are defined)

- [ ] **Step 1: Add `getTraps` to `frontend/src/services/api.js`**

```js
export const getTraps = async (params = {}) => {
    const response = await api.get('/metrics/traps', { params });
    return response.data;
};
```

- [ ] **Step 2: Create `frontend/src/components/TrapsPage.js`**

```jsx
import React, { useState, useEffect } from 'react';
import { getTraps, getDevices } from '../services/api';

const TIME_RANGES = [
    { label: '1h',  hours: 1 },
    { label: '6h',  hours: 6 },
    { label: '24h', hours: 24 },
    { label: '7d',  hours: 168 },
];

export default function TrapsPage() {
    const [traps, setTraps] = useState([]);
    const [devices, setDevices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [hours, setHours] = useState(24);
    const [deviceFilter, setDeviceFilter] = useState('');
    const [oidFilter, setOidFilter] = useState('');

    useEffect(() => {
        getDevices().then(setDevices).catch(() => {});
    }, []);

    useEffect(() => {
        load();
        const iv = setInterval(load, 30000);
        return () => clearInterval(iv);
    }, [hours, deviceFilter, oidFilter]);

    const load = async () => {
        setLoading(true);
        try {
            const params = { hours, limit: 200 };
            if (deviceFilter) params.device_id = deviceFilter;
            if (oidFilter) params.trap_oid = oidFilter;
            setTraps(await getTraps(params));
        } catch {
            // non-fatal
        } finally {
            setLoading(false);
        }
    };

    const deviceName = (ip) => {
        const d = devices.find(d => d.ip_address === ip);
        return d ? d.name : ip;
    };

    return (
        <div className="fade-in">
            <div className="page-header">
                <div>
                    <div className="page-title">SNMP Traps</div>
                    <div className="page-subtitle">Incoming trap events from devices</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                        className="input table-search"
                        type="search"
                        placeholder="Filter by OID…"
                        value={oidFilter}
                        onChange={e => setOidFilter(e.target.value)}
                    />
                    <select
                        className="input"
                        value={deviceFilter}
                        onChange={e => setDeviceFilter(e.target.value)}
                        style={{ width: 'auto' }}
                    >
                        <option value="">All devices</option>
                        {devices.map(d => (
                            <option key={d.id} value={d.id}>{d.name}</option>
                        ))}
                    </select>
                    <div style={{ display: 'flex', gap: 4 }}>
                        {TIME_RANGES.map(r => (
                            <button
                                key={r.label}
                                onClick={() => setHours(r.hours)}
                                style={{
                                    background: hours === r.hours ? 'var(--color-accent)' : 'var(--color-bg)',
                                    color: hours === r.hours ? '#fff' : 'var(--color-text-muted)',
                                    border: `1px solid ${hours === r.hours ? 'var(--color-accent)' : 'var(--color-border)'}`,
                                    padding: '2px 8px', borderRadius: 4, fontSize: 11, cursor: 'pointer',
                                }}
                            >
                                {r.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Received</th>
                            <th>Device</th>
                            <th>Trap OID</th>
                            <th>Varbinds</th>
                            <th>Agent</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading && (
                            <tr>
                                <td colSpan="5" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                                    Loading…
                                </td>
                            </tr>
                        )}
                        {!loading && traps.length === 0 && (
                            <tr>
                                <td colSpan="5" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--color-text-faint)' }}>
                                    No traps received in the last {hours === 1 ? '1 hour' : hours < 24 ? `${hours} hours` : hours === 24 ? '24 hours' : '7 days'}.
                                    {' '}Enable <code>TRAP_ENABLED=true</code> on the agent to start receiving traps.
                                </td>
                            </tr>
                        )}
                        {!loading && traps.map((trap, i) => (
                            <tr key={i}>
                                <td className="font-mono text-sm text-muted">
                                    {new Date(trap.received_at).toLocaleString()}
                                </td>
                                <td>{deviceName(trap.device_ip)}</td>
                                <td className="font-mono text-xs">{trap.trap_oid}</td>
                                <td>
                                    <details>
                                        <summary style={{ cursor: 'pointer', fontSize: 11, color: 'var(--color-text-muted)' }}>
                                            {Object.keys(JSON.parse(trap.varbinds || '{}')).length} vars
                                        </summary>
                                        <pre style={{ fontSize: 10, marginTop: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--color-text-faint)' }}>
                                            {JSON.stringify(JSON.parse(trap.varbinds || '{}'), null, 2)}
                                        </pre>
                                    </details>
                                </td>
                                <td className="font-mono text-xs text-muted">{trap.agent_id?.slice(0, 14)}…</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
```

- [ ] **Step 3: Add Traps to the sidebar**

In `frontend/src/components/Sidebar.js`, find the existing nav items and add a Traps entry. Match the exact pattern used for other nav items. The route path should be `/traps`.

- [ ] **Step 4: Register the route**

In `frontend/src/App.js` (or wherever React Router routes are defined), import `TrapsPage` and add:
```jsx
<Route path="/traps" element={<PrivateRoute><TrapsPage /></PrivateRoute>} />
```

- [ ] **Step 5: Build frontend and verify in browser**

```bash
docker-compose build frontend && docker-compose up -d frontend
```

Open http://localhost → Traps in sidebar. Verify:
- Page loads showing empty state with helpful message
- Time range buttons switch the query window
- Device and OID filters work
- Varbinds expand/collapse via `<details>`
- Auto-refreshes every 30s

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/api.js frontend/src/components/TrapsPage.js \
        frontend/src/components/Sidebar.js frontend/src/App.js
git commit -m "feat: Traps page with time-range, device and OID filters"
```

---

### Task 7: End-to-end test with simulator

The SNMP simulator doesn't emit traps by default. Use `snmptrap` from within the agent container to send a test trap and verify the full pipeline.

- [ ] **Step 1: Enable trap ingestion on the agent**

Add to `.env`:
```bash
TRAP_ENABLED=true
TRAP_LISTEN_PORT=162
TRAP_COMMUNITY=public
```

Rebuild and restart:
```bash
docker-compose up -d --build agent
docker-compose logs agent --tail=20
```

Expected log line: `Trap listener started on UDP port 162 (community: public)`

- [ ] **Step 2: Send a test trap from inside the docker network**

```bash
docker-compose exec agent sh -c \
  "snmptrap -v 2c -c public manager:162 '' 1.3.6.1.6.3.1.1.5.3 1.3.6.1.2.1.2.2.1.1.1 i 1"
```

If `snmptrap` is not available in the agent image, send from the snmp-simulator container:
```bash
docker-compose exec snmp-simulator sh -c \
  "snmptrap -v 2c -c public agent:162 '' 1.3.6.1.6.3.1.1.5.3"
```

- [ ] **Step 3: Verify trap received and uploaded**

```bash
# Check agent log
docker-compose logs agent --tail=10

# Check manager stored it
curl -s "http://localhost:8001/internal/metrics/traps?hours=1&limit=5" \
  -H "Authorization: Bearer change-me-in-production" | python3 -m json.tool
```

Expected: at least one trap row with the OID sent.

- [ ] **Step 4: Verify it shows in the UI**

Open http://localhost → Traps → select 1h range → trap row should appear.

- [ ] **Step 5: Commit final state**

```bash
git add .env.example
git commit -m "docs: add TRAP_ENABLED env var to .env.example"
```
