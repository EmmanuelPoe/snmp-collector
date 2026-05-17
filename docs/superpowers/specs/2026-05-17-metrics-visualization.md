# Metrics Visualization Enhancements — Design Spec

**Date:** 2026-05-17
**Scope:** Two frontend-only enhancements to improve metrics readability
**Files changed:** `InterfaceCard.js`, `Dashboard.js`
**Backend changes:** None

---

## Feature 1 — Enhanced Interface Card Sparklines

### Current State
`InterfaceCard.js` has a `Sparkline` component that receives `data.sparkline` (array of `{timestamp, in_bps, out_bps}`) but only renders `in_bps` as blue bars. `out_bps` is ignored. Errors (`data.error_count`) are shown as a number in the stat grid but have no visual in the sparkline.

### Change
- Render both `in_bps` (blue, `#3b82f6`) and `out_bps` (green, `#10b981`) as separate bar groups side by side within each time slot
- If `error_count > 0`, add a red top border (`2px solid #ef4444`) to the sparkline container so errors are visible at a glance without reading the stat number
- No data fetching changes — sparkline data already flows from `getInterfaceRates()` via `DeviceMetrics.js`

### Data shape (unchanged)
```js
data.sparkline = [{ timestamp: string, in_bps: number, out_bps: number }, ...]
data.error_count = number  // already present
```

### Layout
Each time slot renders two side-by-side bars (in/out), scaled to the max value across all points. A small legend (`● In  ● Out`) sits below the sparkline. The sparkline container gets `border-top: 2px solid #ef4444` when `error_count > 0`, transparent otherwise.

---

## Feature 2 — Per-Device Traffic Overview on Dashboard

### Current State
`Dashboard.js` calls `getMetrics({ limit: 100 })` and passes results through `buildTrafficSeries()` which aggregates all devices into a single line chart. Colors use old dark-theme amber (`#fbbf24`) and a dark tooltip style that clashes with the current light theme.

### Change
Replace the aggregate chart with a per-device `LineChart`:
- On load (and on time range change), call `getInterfaceRates(deviceId)` for each device in parallel
- For each device, sum `in_bps + out_bps` across all interfaces per minute bucket to get total device throughput
- Plot one `<Line>` per device on a shared `<LineChart>`, each line auto-colored from a fixed palette: `['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444']`
- Add a time range selector (1h / 6h / 24h) — passed as `hours` param to `getInterfaceRates()`
- Update chart colors to match light theme: axis text `#64748b`, grid `#e2e8f0`, tooltip background `#fff` with `#e2e8f0` border
- Keep the `buildTrafficSeries` helper but rename/replace it with `buildPerDeviceSeries(ratesMap)`

### Data flow
```
Dashboard.loadData()
  → getDevices()                          // existing
  → getInterfaceRates(id) × N devices     // replaces getMetrics({ limit:100 })
  → buildPerDeviceSeries(deviceId, ratesData)
    → sum in_bps+out_bps across interfaces per minute bucket
    → return [{ time: "14:05", "Test-Simulator": 24300, "Router-02": 8100 }, ...]
  → <LineChart> with one <Line> per device name key
```

### Time range selector
Three buttons (1h / 6h / 24h), styled with the design system (`background: var(--color-accent)` for active). State lives in `Dashboard` component. Passed as `hours` to `getInterfaceRates()`.

### Edge cases
- Device with no data in the selected range: line simply absent (recharts skips undefined values)
- `getInterfaceRates()` failure for one device: caught individually, that device omitted from chart
- Zero devices: show "No devices configured" placeholder instead of chart

---

## Out of Scope
- Backend aggregation endpoint (not needed at current device counts)
- Sparkline changes to `InterfacePanel.js` (already has full recharts charts)
- Any change to `DeviceMetrics.js` (data flow is unchanged)
