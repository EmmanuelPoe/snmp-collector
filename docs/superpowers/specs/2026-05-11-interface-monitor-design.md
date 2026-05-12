# Interface Monitor — Design Spec

**Date:** 2026-05-11  
**Status:** Approved  
**Replaces:** MetricsViewer.js (current explorer model)

---

## Goal

Replace the current metrics explorer (Device → Module → Interface → checkbox drill-down) with a production-grade interface monitor: a live-refreshing overview grid of all interfaces per device, with a slide-in panel for detailed charts on any selected interface.

Primary use case: watching interface traffic graphs in a NOC or ops context.

---

## Interaction Model

1. User selects a device from a dropdown (or arrives via `?device_id=` URL param — existing behaviour preserved)
2. Page shows a **grid of interface cards** — one per interface discovered in DuckDB for that device
3. A **Live badge** shows the page auto-refreshes every 60 seconds (matching agent poll interval)
4. Clicking any card opens a **slide-in panel** from the right — detailed charts for that interface
5. Clicking another card switches the panel; clicking ✕ closes it
6. DOWN interfaces are shown dimmed but still present in the grid

---

## Architecture

### New endpoints

**Manager** — `GET /internal/metrics/rates`

Parameters: `device_ip` (required), `hours` (default: 1)

Returns per-interface rate data computed from raw DuckDB rows:

```json
{
  "interfaces": {
    "GigabitEthernet0/1": {
      "status": "up",
      "speed_bps": 1000000000,
      "current_in_bps": 56250000,
      "current_out_bps": 15000000,
      "utilization_pct": 4.5,
      "error_count": 2,
      "sparkline": [
        {"timestamp": "2026-05-11T22:00:00Z", "in_bps": 51200000, "out_bps": 12800000},
        ...
      ]
    }
  }
}
```

Rate calculation: fetch all rows for `device_ip` in the last `hours` window, group by `(interface_name, oid_name)`, sort by `collected_at`, compute `(v2 - v1) / (t2 - t1).total_seconds()` between consecutive rows. Current rate = most recent delta. Sparkline = all deltas in time order.

**Status:** derived from the latest `ifOperStatus` row per interface (value `1` = up, `2` = down, anything else = unknown). If no `ifOperStatus` row exists for an interface, status is omitted.

**Speed:** derived from the latest `ifHighSpeed` row (in Mbps, multiply by 1,000,000 to get bps) if present, else `ifSpeed` (already in bps). If neither OID is present for an interface, `speed_bps` is `null`.

Utilization: `max(current_in_bps, current_out_bps) * 8 / speed_bps * 100`. If `speed_bps` is `null`, utilization is omitted (`null`).

Counter wrap handling: if `v2 < v1`, treat the delta as 0 (conservative — avoids spike artifacts from 32-bit counter wraps).

**Backend** — `GET /metrics/rates/{device_id}`

Thin proxy to the manager endpoint. Same pattern as existing `GET /metrics/available/{device_id}`. Resolves `device_id → ip_address` via Postgres, calls `GET /internal/metrics/rates?device_ip=...`, returns the response unchanged.

### Existing endpoints reused

- `GET /metrics` — panel drilldown fetches raw time-series for a specific interface; frontend computes bps deltas for the panel charts
- `GET /devices` — device selector dropdown (unchanged)
- `GET /metrics/available/{device_id}` — not used by the new page; can be removed later

---

## Frontend Components

### `DeviceMetrics.js` (replaces `MetricsViewer.js`)

Top-level page component. Owns:
- Device selector state + URL param sync (`?device_id=`)
- `ratesData` state — result of `getInterfaceRates(deviceId)`
- `selectedInterface` state — which card is open in the panel
- 60-second auto-refresh interval (clears on unmount and device change)
- Renders: page header, device dropdown, live badge, `InterfaceGrid`, `InterfacePanel` (conditionally)

Route stays `/metrics`. The existing `<Route>` in `App.js` just swaps the component.

### `InterfaceCard.js`

Props: `iface` (interface name), `data` (rates object for this interface), `isActive` (bool), `onClick`

Renders:
- Interface name + alias (from `ifAlias` OID if available, else blank)
- Status badge (UP/DOWN, link speed if known)
- Stacked sparkline: blue bars for in_bps, green overlay bars for out_bps, normalised to the max value across all sparkline points
- Summary row: In bps | Out bps | Util % | Error count
- Utilization % turns red at ≥ 80%
- DOWN cards render at 60% opacity

### `InterfacePanel.js`

Props: `deviceId`, `iface` (interface name), `onClose`

Owns:
- `timeRange` state (1h/6h/24h/7d, default 1h)
- Raw time-series fetch (`getMetrics`) triggered on mount and timeRange change
- Local delta computation: sort rows by `collected_at`, compute consecutive bps deltas per oid_name, produce `chartData` array for Recharts

Renders:
- Panel header: interface name, alias, status, speed; ✕ close button
- Time range toolbar: 1h | 6h | 24h | 7d buttons
- Stats row: current In bps | Out bps | Utilization %
- **Network Traffic** chart (AreaChart): `ifInOctets`/`ifOutOctets` or HC variants, y-axis in bps
- **Errors & Discards** chart (LineChart): `ifInErrors`, `ifOutErrors`, `ifInDiscards`, `ifOutDiscards`
- Additional chart groups rendered only when those OIDs are present in the data (packet throughput, link status) — same grouping logic as current MetricsViewer

### `api.js` addition

```js
export const getInterfaceRates = async (deviceId) => {
  const response = await api.get(`/metrics/rates/${deviceId}`);
  return response.data;
};
```

---

## Data Flow

```
[60s interval]
    │
    ▼
DeviceMetrics calls getInterfaceRates(deviceId)
    │
    ▼
Backend GET /metrics/rates/{device_id}
    │  resolves device_id → ip_address
    ▼
Manager GET /internal/metrics/rates?device_ip=...
    │  fetches last 1h raw rows from DuckDB
    │  computes deltas in Python
    ▼
Returns: { interfaces: { "Gi0/1": { sparkline, current_in_bps, ... } } }
    │
    ▼
DeviceMetrics renders InterfaceCard × N (grid)

[User clicks card]
    │
    ▼
InterfacePanel mounts, calls getMetrics({ device_id, interface_name, start_time, end_time })
    │
    ▼
Backend GET /metrics → Manager GET /internal/metrics
    │  returns raw rows for selected interface + time range
    ▼
InterfacePanel computes deltas locally → Recharts AreaChart/LineChart
```

---

## Auto-Refresh

`DeviceMetrics` sets a `setInterval` of 60,000ms that re-calls `getInterfaceRates`. The interval is cleared on:
- Component unmount
- Device change (a new interval starts after the new device loads)

The open panel does **not** auto-refresh its charts — the user controls that via the time range buttons. This avoids jarring chart redraws while the user is actively reading it.

---

## Files Changed

| File | Change |
|---|---|
| `manager/routers/metrics.py` | Add `GET /internal/metrics/rates` endpoint |
| `backend/routers/metrics.py` | Add `GET /metrics/rates/{device_id}` proxy |
| `frontend/src/services/api.js` | Add `getInterfaceRates(deviceId)` |
| `frontend/src/components/DeviceMetrics.js` | New — replaces MetricsViewer |
| `frontend/src/components/InterfaceCard.js` | New |
| `frontend/src/components/InterfacePanel.js` | New |
| `frontend/src/App.js` | Swap `MetricsViewer` import for `DeviceMetrics` on `/metrics` route |
| `frontend/src/components/MetricsViewer.js` | Delete |
| `frontend/src/components/DeviceManagement.js` | No change — Charts button already navigates to `/metrics?device_id=` |

---

## Edge Cases

- **No data for device**: show empty grid with "No interfaces discovered yet" message
- **Single-poll device** (only one row — can't compute a delta): show 0 bps with a tooltip "Waiting for second poll"
- **Counter wrap**: delta < 0 → treat as 0
- **ifSpeed = 0 or missing**: omit utilization %, show `—`
- **Panel opened while refresh fires**: refresh updates card data only; panel charts are independent and not disrupted

---

## Out of Scope

- Multi-device comparison view
- Alert thresholds / notifications
- Historical data beyond 7 days
- Packet-level deep dive
- ifAlias display (include if the OID is already being collected; don't add new OID collection for it)
