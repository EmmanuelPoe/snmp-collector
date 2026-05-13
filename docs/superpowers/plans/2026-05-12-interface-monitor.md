# Interface Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MetricsViewer with a live-refreshing interface overview grid + slide-in panel drilldown for production network monitoring.

**Architecture:** A new manager endpoint computes per-interface bps rates from raw DuckDB rows; the backend proxies it; three new React components (DeviceMetrics, InterfaceCard, InterfacePanel) replace MetricsViewer.js. Cards auto-refresh every 60s. The panel fetches raw time-series and computes deltas locally for charts.

**Tech Stack:** FastAPI (manager + backend), DuckDB, React, Recharts, react-router-dom

---

## File Map

| File | Action |
|---|---|
| `manager/routers/metrics.py` | Modify — add `GET /internal/metrics/rates` |
| `manager/tests/test_metrics_api.py` | Create — rates endpoint tests |
| `backend/routers/metrics.py` | Modify — add `GET /metrics/rates/{device_id}` |
| `backend/tests/test_metrics_router.py` | Create — proxy test |
| `frontend/src/services/api.js` | Modify — add `getInterfaceRates` |
| `frontend/src/App.css` | Modify — add `@keyframes pulse` |
| `frontend/src/components/InterfaceCard.js` | Create |
| `frontend/src/components/InterfacePanel.js` | Create |
| `frontend/src/components/DeviceMetrics.js` | Create |
| `frontend/src/App.js` | Modify — swap MetricsViewer import |
| `frontend/src/components/MetricsViewer.js` | Delete |

---

## Task 1: Manager rates endpoint

**Files:**
- Modify: `manager/routers/metrics.py`
- Create: `manager/tests/test_metrics_api.py`

- [ ] **Step 1: Create the test file**

```python
# manager/tests/test_metrics_api.py
import pytest
from datetime import datetime, timezone, timedelta


def _seed(conn, rows):
    conn.executemany(
        "INSERT INTO snmp_polls "
        "(agent_id, device_ip, interface_name, oid_name, oid, value, collected_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def test_rates_basic_delta(client, auth_headers):
    from db import get_db
    t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = t1 + timedelta(seconds=60)
    _seed(get_db(), [
        # (7000000 - 1000000) / 60 = 100000 B/s * 8 = 800000 bps in
        ("ag1", "10.0.0.1", "Gi0/1", "ifInOctets",    ".1", "1000000",     t1),
        ("ag1", "10.0.0.1", "Gi0/1", "ifInOctets",    ".1", "7000000",     t2),
        # (2000000 - 500000) / 60 = 25000 B/s * 8 = 200000 bps out
        ("ag1", "10.0.0.1", "Gi0/1", "ifOutOctets",   ".2", "500000",      t1),
        ("ag1", "10.0.0.1", "Gi0/1", "ifOutOctets",   ".2", "2000000",     t2),
        ("ag1", "10.0.0.1", "Gi0/1", "ifOperStatus",  ".3", "1",           t2),
        ("ag1", "10.0.0.1", "Gi0/1", "ifSpeed",       ".4", "1000000000",  t2),
    ])

    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.1", headers=auth_headers)
    assert resp.status_code == 200
    iface = resp.json()["interfaces"]["Gi0/1"]

    assert iface["current_in_bps"] == pytest.approx(800000, rel=0.01)
    assert iface["current_out_bps"] == pytest.approx(200000, rel=0.01)
    assert iface["status"] == "up"
    assert iface["speed_bps"] == 1_000_000_000
    # util = max(800000, 200000) / 1e9 * 100 = 0.08
    assert iface["utilization_pct"] == pytest.approx(0.08, rel=0.05)
    assert len(iface["sparkline"]) == 1
    assert iface["sparkline"][0]["in_bps"] == pytest.approx(800000, rel=0.01)


def test_rates_counter_wrap_returns_zero(client, auth_headers):
    from db import get_db
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = t1 + timedelta(seconds=60)
    _seed(get_db(), [
        ("ag1", "10.0.0.2", "Gi0/1", "ifInOctets", ".1", "4294967295", t1),
        ("ag1", "10.0.0.2", "Gi0/1", "ifInOctets", ".1", "1000",       t2),
    ])
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.2", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["interfaces"]["Gi0/1"]["current_in_bps"] == 0.0


def test_rates_ifhighspeed_preferred_over_ifspeed(client, auth_headers):
    from db import get_db
    t2 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _seed(get_db(), [
        # ifHighSpeed = 1000 Mbps → 1_000_000_000 bps
        ("ag1", "10.0.0.3", "Gi0/1", "ifHighSpeed", ".1", "1000", t2),
        ("ag1", "10.0.0.3", "Gi0/1", "ifSpeed",     ".2", "10000000", t2),  # should be ignored
    ])
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.3", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["interfaces"]["Gi0/1"]["speed_bps"] == 1_000_000_000


def test_rates_unknown_device_returns_empty(client, auth_headers):
    resp = client.get("/internal/metrics/rates?device_ip=99.99.99.99", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"interfaces": {}}


def test_rates_requires_auth(client):
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.1")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run the tests to confirm they all fail**

```bash
docker-compose exec manager pytest tests/test_metrics_api.py -v
```

Expected: All tests fail with `404` (endpoint doesn't exist yet).

- [ ] **Step 3: Implement the rates endpoint**

Add this import at the top of `manager/routers/metrics.py`:
```python
from datetime import timedelta, timezone, datetime as _dt
```

Add this endpoint after the existing `available_metrics` function in `manager/routers/metrics.py`:

```python
@router.get("/rates")
async def interface_rates(
    device_ip: str,
    hours: float = Query(default=1.0, gt=0, le=168),
    _: str = Depends(require_api_key),
):
    cutoff = _dt.now(timezone.utc) - timedelta(hours=hours)
    rows = await query(
        "SELECT interface_name, oid_name, TRY_CAST(value AS DOUBLE), collected_at "
        "FROM snmp_polls "
        "WHERE device_ip = ? AND collected_at >= ? AND interface_name IS NOT NULL "
        "ORDER BY interface_name, oid_name, collected_at ASC",
        [device_ip, cutoff],
    )

    # Group by (interface_name, oid_name) → list of (value, timestamp)
    oid_series: dict[str, dict[str, list]] = {}
    for iface, oid_name, value, ts in rows:
        oid_series.setdefault(iface, {}).setdefault(oid_name, []).append((value, ts))

    def _deltas(pts: list) -> list:
        result = []
        for i in range(1, len(pts)):
            v1, t1 = pts[i - 1]
            v2, t2 = pts[i]
            if v1 is None or v2 is None:
                continue
            dt_sec = (t2 - t1).total_seconds()
            if dt_sec <= 0:
                continue
            result.append((max(0.0, v2 - v1) / dt_sec, t2))
        return result

    interfaces: dict = {}
    for iface, oids in oid_series.items():
        in_pts = oids.get("ifHCInOctets") or oids.get("ifInOctets", [])
        out_pts = oids.get("ifHCOutOctets") or oids.get("ifOutOctets", [])
        in_d = _deltas(in_pts)
        out_d = _deltas(out_pts)

        current_in_bps = in_d[-1][0] * 8 if in_d else 0.0
        current_out_bps = out_d[-1][0] * 8 if out_d else 0.0

        # Build sparkline aligned by index (same poll interval → same length)
        n = max(len(in_d), len(out_d))
        sparkline = []
        for i in range(n):
            in_val = in_d[i][0] * 8 if i < len(in_d) else 0.0
            out_val = out_d[i][0] * 8 if i < len(out_d) else 0.0
            ts = (in_d[i][1] if i < len(in_d) else out_d[i][1])
            sparkline.append({"timestamp": ts.isoformat(), "in_bps": in_val, "out_bps": out_val})

        # Status from latest ifOperStatus (1=up, 2=down)
        status = None
        if "ifOperStatus" in oids and oids["ifOperStatus"]:
            sv = oids["ifOperStatus"][-1][0]
            if sv is not None:
                status = {1.0: "up", 2.0: "down"}.get(sv, "unknown")

        # Speed: prefer ifHighSpeed (Mbps → bps), fallback to ifSpeed (already bps)
        speed_bps = None
        if "ifHighSpeed" in oids and oids["ifHighSpeed"]:
            v = oids["ifHighSpeed"][-1][0]
            if v is not None and v > 0:
                speed_bps = v * 1_000_000
        elif "ifSpeed" in oids and oids["ifSpeed"]:
            v = oids["ifSpeed"][-1][0]
            if v is not None and v > 0:
                speed_bps = v

        # Utilization: max(in, out) / link_speed * 100
        util = None
        if speed_bps:
            util = round(max(current_in_bps, current_out_bps) / speed_bps * 100, 1)

        # Error count: sum of error rate deltas over the window
        error_count = 0
        for err_oid in ("ifInErrors", "ifOutErrors"):
            if err_oid in oids:
                for d_val, _ in _deltas(oids[err_oid]):
                    error_count += int(d_val)

        interfaces[iface] = {
            "status": status,
            "speed_bps": speed_bps,
            "current_in_bps": current_in_bps,
            "current_out_bps": current_out_bps,
            "utilization_pct": util,
            "error_count": error_count,
            "sparkline": sparkline,
        }

    return {"interfaces": interfaces}
```

- [ ] **Step 4: Run the tests and confirm they all pass**

```bash
docker-compose exec manager pytest tests/test_metrics_api.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run full manager test suite to check for regressions**

```bash
docker-compose exec manager pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add manager/routers/metrics.py manager/tests/test_metrics_api.py
git commit -m "feat(manager): add GET /internal/metrics/rates endpoint with bps delta computation"
```

---

## Task 2: Backend rates proxy

**Files:**
- Modify: `backend/routers/metrics.py`
- Create: `backend/tests/test_metrics_router.py`

- [ ] **Step 1: Create the test file**

```python
# backend/tests/test_metrics_router.py
import pytest
import httpx
from models import Device


@pytest.fixture
def device(db_session):
    d = Device(name="test-switch", ip_address="10.0.0.1")
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)
    return d


def test_rates_proxy_returns_manager_response(client, admin_headers, device, respx_mock):
    manager_payload = {
        "interfaces": {
            "Gi0/1": {
                "status": "up",
                "speed_bps": 1000000000,
                "current_in_bps": 800000.0,
                "current_out_bps": 200000.0,
                "utilization_pct": 0.08,
                "error_count": 0,
                "sparkline": [],
            }
        }
    }
    respx_mock.get("http://manager:8000/internal/metrics/rates").mock(
        return_value=httpx.Response(200, json=manager_payload)
    )

    resp = client.get(f"/metrics/rates/{device.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "Gi0/1" in data["interfaces"]
    assert data["interfaces"]["Gi0/1"]["current_in_bps"] == 800000.0


def test_rates_proxy_404_for_unknown_device(client, admin_headers):
    resp = client.get("/metrics/rates/9999", headers=admin_headers)
    assert resp.status_code == 404


def test_rates_proxy_requires_auth(client, device):
    resp = client.get(f"/metrics/rates/{device.id}")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to confirm they fail**

```bash
docker-compose exec backend pytest tests/test_metrics_router.py -v
```

Expected: `test_rates_proxy_returns_manager_response` and `test_rates_proxy_requires_auth` fail with 404 (route missing). `test_rates_proxy_404_for_unknown_device` may pass incidentally.

- [ ] **Step 3: Add the proxy endpoint to `backend/routers/metrics.py`**

Add this function after `get_available_metrics`:

```python
@router.get("/rates/{device_id}")
def get_interface_rates(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device_ip = _device_ip(device_id, db)
    return _manager_get("/rates", {"device_ip": device_ip})
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
docker-compose exec backend pytest tests/test_metrics_router.py -v
```

Expected: All 3 tests pass.

- [ ] **Step 5: Run full backend test suite**

```bash
docker-compose exec backend pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/metrics.py backend/tests/test_metrics_router.py
git commit -m "feat(backend): add GET /metrics/rates/{device_id} proxy to manager rates endpoint"
```

---

## Task 3: Frontend api.js + CSS pulse animation

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Add `getInterfaceRates` to api.js**

In `frontend/src/services/api.js`, add after `getInterfaceStats`:

```js
export const getInterfaceRates = async (deviceId) => {
    const response = await api.get(`/metrics/rates/${deviceId}`);
    return response.data;
};
```

- [ ] **Step 2: Add pulse keyframe to App.css**

In `frontend/src/App.css`, add at the end of the file:

```css
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js frontend/src/App.css
git commit -m "feat(frontend): add getInterfaceRates API call and pulse keyframe"
```

---

## Task 4: InterfaceCard component

**Files:**
- Create: `frontend/src/components/InterfaceCard.js`

- [ ] **Step 1: Create the file**

```jsx
// frontend/src/components/InterfaceCard.js
import React from 'react';

function formatBps(bps) {
    if (bps === null || bps === undefined) return '—';
    if (bps >= 1e9) return (bps / 1e9).toFixed(1) + ' Gbps';
    if (bps >= 1e6) return (bps / 1e6).toFixed(1) + ' Mbps';
    if (bps >= 1e3) return (bps / 1e3).toFixed(1) + ' Kbps';
    return bps.toFixed(0) + ' bps';
}

function Sparkline({ sparkline }) {
    if (!sparkline || sparkline.length === 0) {
        return (
            <div style={{ height: 48, background: 'rgba(0,0,0,0.2)', borderRadius: 4 }} />
        );
    }
    const maxVal = Math.max(...sparkline.map(p => Math.max(p.in_bps, p.out_bps)), 1);
    return (
        <div style={{
            height: 48, display: 'flex', alignItems: 'flex-end', gap: 1,
            background: 'rgba(0,0,0,0.2)', borderRadius: 4, padding: 2, overflow: 'hidden',
        }}>
            {sparkline.map((pt, i) => (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}>
                    <div style={{
                        background: 'rgba(59,130,246,0.7)',
                        height: `${Math.max((pt.in_bps / maxVal) * 100, 1)}%`,
                        borderRadius: '1px 1px 0 0',
                    }} />
                </div>
            ))}
        </div>
    );
}

function InterfaceCard({ iface, data, isActive, onClick }) {
    const isDown = data.status === 'down';
    const highUtil = data.utilization_pct != null && data.utilization_pct >= 80;

    return (
        <div
            onClick={onClick}
            style={{
                background: isActive ? '#1a2744' : '#1e293b',
                border: `1px solid ${isActive ? '#3b82f6' : '#334155'}`,
                boxShadow: isActive ? '0 0 0 2px rgba(59,130,246,0.25)' : 'none',
                borderRadius: 10,
                padding: 14,
                cursor: 'pointer',
                opacity: isDown ? 0.6 : 1,
                transition: 'border-color 0.15s, box-shadow 0.15s',
            }}
        >
            {/* Header row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {iface}
                    </div>
                    {data.alias && (
                        <div style={{ fontSize: 10, color: '#64748b', marginTop: 1 }}>{data.alias}</div>
                    )}
                </div>
                <span style={{
                    fontSize: 10, padding: '2px 7px', borderRadius: 10, fontWeight: 600, whiteSpace: 'nowrap', marginLeft: 8,
                    background: isDown ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)',
                    color: isDown ? '#ef4444' : '#10b981',
                    border: `1px solid ${isDown ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}`,
                }}>
                    {(data.status ?? 'unknown').toUpperCase()}
                    {data.speed_bps && !isDown ? ` · ${formatBps(data.speed_bps)}` : ''}
                </span>
            </div>

            {/* Sparkline */}
            <div style={{ marginBottom: 10 }}>
                <Sparkline sparkline={data.sparkline} />
            </div>

            {/* Summary row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 6, textAlign: 'center' }}>
                {[
                    { val: formatBps(data.current_in_bps), lbl: 'In', color: '#3b82f6' },
                    { val: formatBps(data.current_out_bps), lbl: 'Out', color: '#10b981' },
                    { val: data.utilization_pct != null ? `${data.utilization_pct}%` : '—', lbl: 'Util', color: highUtil ? '#ef4444' : '#f59e0b' },
                    { val: data.error_count ?? 0, lbl: 'Errors', color: (data.error_count ?? 0) > 0 ? '#ef4444' : '#64748b' },
                ].map(({ val, lbl, color }) => (
                    <div key={lbl}>
                        <div style={{ fontSize: 12, fontWeight: 600, color }}>{val}</div>
                        <div style={{ fontSize: 9, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 1 }}>{lbl}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default InterfaceCard;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/InterfaceCard.js
git commit -m "feat(frontend): add InterfaceCard component with sparkline and summary row"
```

---

## Task 5: InterfacePanel component

**Files:**
- Create: `frontend/src/components/InterfacePanel.js`

- [ ] **Step 1: Create the file**

```jsx
// frontend/src/components/InterfacePanel.js
import React, { useState, useEffect } from 'react';
import {
    AreaChart, Area, LineChart, Line,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { getMetrics } from '../services/api';

const TIME_RANGES = [
    { label: '1h', hours: 1 },
    { label: '6h', hours: 6 },
    { label: '24h', hours: 24 },
    { label: '7d', hours: 168 },
];

function formatBps(bps) {
    if (bps === null || bps === undefined) return 'N/A';
    if (bps >= 1e9) return (bps / 1e9).toFixed(2) + ' Gbps';
    if (bps >= 1e6) return (bps / 1e6).toFixed(2) + ' Mbps';
    if (bps >= 1e3) return (bps / 1e3).toFixed(2) + ' Kbps';
    return bps.toFixed(0) + ' bps';
}

function computeDeltas(rows) {
    // Group by oid_name, sort each group by timestamp ascending
    const byOid = {};
    for (const row of rows) {
        if (!byOid[row.oid_name]) byOid[row.oid_name] = [];
        byOid[row.oid_name].push({ ts: new Date(row.timestamp).getTime(), value: Number(row.value) });
    }
    for (const oid of Object.keys(byOid)) {
        byOid[oid].sort((a, b) => a.ts - b.ts);
    }

    function deltas(pts) {
        const result = [];
        for (let i = 1; i < pts.length; i++) {
            const dt = (pts[i].ts - pts[i - 1].ts) / 1000;
            if (dt <= 0) continue;
            const dv = Math.max(0, pts[i].value - pts[i - 1].value);
            result.push({ ts: pts[i].ts, rate: dv / dt });
        }
        return result;
    }

    const inOctets  = deltas(byOid['ifHCInOctets']  || byOid['ifInOctets']   || []);
    const outOctets = deltas(byOid['ifHCOutOctets'] || byOid['ifOutOctets']  || []);
    const inErrors  = deltas(byOid['ifInErrors']   || []);
    const outErrors = deltas(byOid['ifOutErrors']  || []);
    const inDisc    = deltas(byOid['ifInDiscards'] || []);
    const outDisc   = deltas(byOid['ifOutDiscards']|| []);

    const refPts = inOctets.length >= outOctets.length ? inOctets : outOctets;

    function nearest(arr, ts) {
        const pt = arr.find(p => Math.abs(p.ts - ts) < 5000);
        return pt ? pt.rate : 0;
    }

    return refPts.map(pt => {
        const d = new Date(pt.ts);
        return {
            timeLabel: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            in_bps:      pt.rate * 8,
            out_bps:     nearest(outOctets, pt.ts) * 8,
            in_errors:   nearest(inErrors,  pt.ts),
            out_errors:  nearest(outErrors, pt.ts),
            in_discards: nearest(inDisc,    pt.ts),
            out_discards:nearest(outDisc,   pt.ts),
        };
    });
}

const CHART_STYLE = { backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 };
const GRID = 'rgba(255,255,255,0.05)';
const AXIS = '#64748b';

function InterfacePanel({ deviceId, iface, ifaceData, onClose }) {
    const [timeRange, setTimeRange] = useState(1);
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadChartData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [deviceId, iface, timeRange]);

    const loadChartData = async () => {
        setLoading(true);
        try {
            const end = new Date();
            const start = new Date(end.getTime() - timeRange * 3600 * 1000);
            const rows = await getMetrics({
                device_id: deviceId,
                interface_name: iface,
                start_time: start.toISOString(),
                end_time: end.toISOString(),
                limit: 10000,
            });
            setChartData(computeDeltas(rows));
        } catch (err) {
            console.error('InterfacePanel: failed to load chart data', err);
        } finally {
            setLoading(false);
        }
    };

    const currentInBps  = ifaceData?.current_in_bps  ?? 0;
    const currentOutBps = ifaceData?.current_out_bps ?? 0;
    const util          = ifaceData?.utilization_pct;
    const hasErrors = chartData.some(d => d.in_errors > 0 || d.out_errors > 0 || d.in_discards > 0 || d.out_discards > 0);

    return (
        <div style={{
            width: 480, background: '#1a2035', borderLeft: '1px solid #334155',
            display: 'flex', flexDirection: 'column', flexShrink: 0, overflow: 'hidden',
        }}>
            {/* Header */}
            <div style={{ padding: '14px 16px', borderBottom: '1px solid #334155', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{iface}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>
                        {(ifaceData?.status ?? 'unknown').toUpperCase()}
                        {ifaceData?.speed_bps ? ` · ${formatBps(ifaceData.speed_bps)}` : ''}
                    </div>
                </div>
                <button
                    onClick={onClose}
                    style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 18, padding: '2px 6px', borderRadius: 4, lineHeight: 1 }}
                >
                    ✕
                </button>
            </div>

            {/* Time range toolbar */}
            <div style={{ padding: '8px 16px', borderBottom: '1px solid #1e293b', display: 'flex', gap: 6, flexShrink: 0 }}>
                {TIME_RANGES.map(({ label, hours }) => (
                    <button
                        key={label}
                        onClick={() => setTimeRange(hours)}
                        style={{
                            background: timeRange === hours ? '#3b82f6' : '#1e293b',
                            border: `1px solid ${timeRange === hours ? '#3b82f6' : '#334155'}`,
                            color: timeRange === hours ? '#fff' : '#94a3b8',
                            padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
                        }}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* Stats row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, padding: '10px 16px', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
                {[
                    { val: formatBps(currentInBps),  lbl: 'In (current)',  color: '#3b82f6' },
                    { val: formatBps(currentOutBps), lbl: 'Out (current)', color: '#10b981' },
                    { val: util != null ? `${util}%` : '—', lbl: 'Utilization', color: (util ?? 0) >= 80 ? '#ef4444' : '#f59e0b' },
                ].map(({ val, lbl, color }) => (
                    <div key={lbl} style={{ background: '#0f172a', borderRadius: 6, padding: '8px 10px' }}>
                        <div style={{ fontSize: 15, fontWeight: 700, color }}>{val}</div>
                        <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>{lbl}</div>
                    </div>
                ))}
            </div>

            {/* Charts */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>Loading...</div>
                ) : chartData.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>No data for this time range.</div>
                ) : (
                    <>
                        {/* Network Traffic */}
                        <div style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                Network Traffic (bps)
                            </div>
                            <ResponsiveContainer width="100%" height={160}>
                                <AreaChart data={chartData}>
                                    <defs>
                                        <linearGradient id="gradIn" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="gradOut" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%"  stopColor="#10b981" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                                    <XAxis dataKey="timeLabel" stroke={AXIS} fontSize={10} />
                                    <YAxis stroke={AXIS} fontSize={10} tickFormatter={v => formatBps(v)} width={72} />
                                    <Tooltip contentStyle={CHART_STYLE} formatter={(v, name) => [formatBps(v), name]} />
                                    <Legend iconType="circle" />
                                    <Area type="monotone" dataKey="in_bps"  stroke="#3b82f6" fill="url(#gradIn)"  name="In"  dot={false} strokeWidth={2} />
                                    <Area type="monotone" dataKey="out_bps" stroke="#10b981" fill="url(#gradOut)" name="Out" dot={false} strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Errors & Discards — only shown when non-zero data present */}
                        {hasErrors && (
                            <div style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
                                <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                    Errors &amp; Discards
                                </div>
                                <ResponsiveContainer width="100%" height={120}>
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                                        <XAxis dataKey="timeLabel" stroke={AXIS} fontSize={10} />
                                        <YAxis stroke={AXIS} fontSize={10} />
                                        <Tooltip contentStyle={CHART_STYLE} />
                                        <Legend iconType="circle" />
                                        <Line type="monotone" dataKey="in_errors"    stroke="#ef4444" dot={false} name="In Errors"    strokeWidth={1.5} />
                                        <Line type="monotone" dataKey="out_errors"   stroke="#f97316" dot={false} name="Out Errors"   strokeWidth={1.5} />
                                        <Line type="monotone" dataKey="in_discards"  stroke="#f59e0b" dot={false} name="In Discards"  strokeWidth={1.5} />
                                        <Line type="monotone" dataKey="out_discards" stroke="#eab308" dot={false} name="Out Discards" strokeWidth={1.5} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

export default InterfacePanel;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/InterfacePanel.js
git commit -m "feat(frontend): add InterfacePanel with time-range selector and bps delta charts"
```

---

## Task 6: DeviceMetrics page, App.js wire-up, and MetricsViewer removal

**Files:**
- Create: `frontend/src/components/DeviceMetrics.js`
- Modify: `frontend/src/App.js`
- Delete: `frontend/src/components/MetricsViewer.js`

- [ ] **Step 1: Create DeviceMetrics.js**

```jsx
// frontend/src/components/DeviceMetrics.js
import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getDevices, getInterfaceRates } from '../services/api';
import InterfaceCard from './InterfaceCard';
import InterfacePanel from './InterfacePanel';

function DeviceMetrics() {
    const [searchParams] = useSearchParams();
    const [devices, setDevices]           = useState([]);
    const [selectedDevice, setSelectedDevice] = useState('');
    const [ratesData, setRatesData]       = useState(null);
    const [selectedIface, setSelectedIface] = useState(null);
    const [loading, setLoading]           = useState(false);
    const intervalRef = useRef(null);

    useEffect(() => {
        loadDevices();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setRatesData(null);
        setSelectedIface(null);
        if (!selectedDevice) return;

        loadRates();
        intervalRef.current = setInterval(loadRates, 60000);
        return () => clearInterval(intervalRef.current);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedDevice]);

    const loadDevices = async () => {
        try {
            const data = await getDevices(true);
            setDevices(data);
            const paramId = searchParams.get('device_id');
            if (paramId) {
                const match = data.find(d => String(d.id) === String(paramId));
                if (match) setSelectedDevice(String(match.id));
            }
        } catch (err) {
            console.error('DeviceMetrics: failed to load devices', err);
        }
    };

    const loadRates = async () => {
        if (!selectedDevice) return;
        setLoading(true);
        try {
            const data = await getInterfaceRates(selectedDevice);
            setRatesData(data);
        } catch (err) {
            console.error('DeviceMetrics: failed to load rates', err);
        } finally {
            setLoading(false);
        }
    };

    const interfaces = ratesData ? Object.entries(ratesData.interfaces) : [];

    return (
        <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Page header */}
            <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexShrink: 0 }}>
                <div className="page-title">Interface Monitor</div>
                <select
                    className="select"
                    value={selectedDevice}
                    onChange={e => setSelectedDevice(e.target.value)}
                    style={{ maxWidth: 300 }}
                >
                    <option value="">Select Device...</option>
                    {devices.map(d => (
                        <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>
                    ))}
                </select>
                {selectedDevice && (
                    <span style={{
                        marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
                        background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)',
                        color: '#10b981', padding: '3px 10px', borderRadius: 12, fontSize: 11,
                    }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block', animation: 'pulse 1.5s infinite' }} />
                        Live · refreshes every 60s
                    </span>
                )}
            </div>

            {/* Content */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                {/* Interface grid */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem' }}>
                    {!selectedDevice && (
                        <div className="text-muted" style={{ textAlign: 'center', marginTop: '3rem' }}>
                            Select a device to begin monitoring.
                        </div>
                    )}
                    {selectedDevice && loading && !ratesData && (
                        <div className="text-muted" style={{ textAlign: 'center', marginTop: '3rem' }}>
                            Loading interfaces...
                        </div>
                    )}
                    {ratesData && interfaces.length === 0 && (
                        <div className="text-muted" style={{ textAlign: 'center', marginTop: '3rem' }}>
                            No interfaces discovered yet.<br />
                            The agent polls every 60 seconds — check back shortly.
                        </div>
                    )}
                    {interfaces.length > 0 && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                            {interfaces.map(([iface, data]) => (
                                <InterfaceCard
                                    key={iface}
                                    iface={iface}
                                    data={data}
                                    isActive={selectedIface === iface}
                                    onClick={() => setSelectedIface(prev => prev === iface ? null : iface)}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* Slide-in panel */}
                {selectedIface && ratesData && (
                    <InterfacePanel
                        deviceId={selectedDevice}
                        iface={selectedIface}
                        ifaceData={ratesData.interfaces[selectedIface]}
                        onClose={() => setSelectedIface(null)}
                    />
                )}
            </div>
        </div>
    );
}

export default DeviceMetrics;
```

- [ ] **Step 2: Update App.js**

In `frontend/src/App.js`:

Replace:
```js
import MetricsViewer from './components/MetricsViewer';
```
With:
```js
import DeviceMetrics from './components/DeviceMetrics';
```

Replace:
```jsx
<Route path="/metrics" element={<PrivateRoute><MetricsViewer /></PrivateRoute>} />
```
With:
```jsx
<Route path="/metrics" element={<PrivateRoute><DeviceMetrics /></PrivateRoute>} />
```

- [ ] **Step 3: Delete MetricsViewer.js**

```bash
rm frontend/src/components/MetricsViewer.js
```

- [ ] **Step 4: Rebuild the frontend container**

```bash
docker-compose build frontend && docker-compose up -d frontend
```

- [ ] **Step 5: Verify the app loads without errors**

Open http://localhost in the browser. Navigate to **Interface Monitor** in the sidebar. Confirm:
- Page loads without console errors
- Device dropdown is populated
- Selecting a device shows interface cards (or the "no data yet" empty state)
- Clicking a card opens the slide-in panel
- Clicking ✕ closes the panel
- Clicking another card switches the panel

- [ ] **Step 6: Run the full manager test suite one final time**

```bash
docker-compose exec manager pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/DeviceMetrics.js frontend/src/App.js
git rm frontend/src/components/MetricsViewer.js
git commit -m "feat(frontend): replace MetricsViewer with DeviceMetrics interface monitor

Live-refreshing grid of interface cards with slide-in panel drilldown.
Cards show in/out bps, utilization %, error count, and a 1h sparkline.
Panel shows full traffic and error charts with 1h/6h/24h/7d time range.
Auto-refreshes every 60s. URL param ?device_id= preserved."
```
