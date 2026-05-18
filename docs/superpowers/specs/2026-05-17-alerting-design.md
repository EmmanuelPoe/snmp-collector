# Alerting — Design Spec

**Date:** 2026-05-17
**Scope:** In-app alerting for device, interface, bandwidth, and agent conditions
**Delivery:** In-app only (dashboard feed, sidebar badge, toast notifications)
**Resolution:** Auto-resolve when condition clears

---

## Overview

A backend background task evaluates four alert conditions every 30 seconds and writes state to Postgres. The frontend polls for active alerts and renders them in a dashboard panel, sidebar badge, and toast notifications. No changes to the agent or manager.

---

## Data Model

### `alerts` table

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| device_id | int FK nullable | null for agent_offline alerts |
| agent_id | str nullable | null for device/interface alerts |
| alert_type | enum | `device_unreachable`, `interface_down`, `bandwidth_threshold`, `agent_offline` |
| message | str | Human-readable description |
| triggered_at | datetime | When alert was first opened |
| resolved_at | datetime nullable | When condition cleared |
| status | enum | `open`, `resolved` |

### `alert_rules` table

| Column | Type | Notes |
|--------|------|-------|
| id | int PK | |
| device_id | int FK | One rule set per device |
| bandwidth_in_pct | float nullable | % of interface speed — null = disabled |
| bandwidth_out_pct | float nullable | % of interface speed — null = disabled |
| error_rate | float nullable | errors/poll threshold — null = disabled |
| enabled | bool | Master switch for this device's rules |

---

## Alert Evaluation (Backend Background Task)

An `asyncio` background task registered at FastAPI startup, runs every 30 seconds.

### Condition checks (in order)

**1. Device unreachable**
- Query DuckDB: devices with no poll data in the last 5 minutes
- Cross-reference against all registered devices in Postgres
- Alert fires for any registered device absent from recent DuckDB results

**2. Interface down**
- Query DuckDB: latest `ifOperStatus` per interface per device
- Alert fires per device where one or more interfaces have status = `down` (ifOperStatus = 2)
- message: `"{device_name} — interfaces down: {iface1}, {iface2}"`
- One open alert per device; message updated on re-evaluation if the set of down interfaces changes

**3. Bandwidth threshold**
- Only evaluated for devices with an enabled `alert_rules` row
- Query DuckDB: latest `in_bps` / `out_bps` per interface for that device
- Interface speed from `ifSpeed` OID (already collected)
- Alert fires if `in_bps / ifSpeed > bandwidth_in_pct/100` or `out_bps / ifSpeed > bandwidth_out_pct/100`
- message: `"{device_name} — {interface_name} in/out at {X}% utilization"`

**4. Agent offline**
- Fetch agent list from manager proxy (existing `/api/agents` endpoint)
- Alert fires for any agent with `status == "offline"` or `last_seen > 3 minutes`
- message: `"Agent {hostname} has gone offline"`

### Deduplication rule

Before creating a new alert, check for an existing `open` alert with the same `(alert_type, device_id, agent_id)`. If one exists, skip. This prevents duplicate rows on every 30s cycle.

### Auto-resolution

On each cycle, after collecting current firing conditions, query all `open` alerts. For each open alert whose condition is no longer detected, set `status = resolved` and `resolved_at = now()`.

---

## API Endpoints

New `alerts.py` router mounted at `/alerts` and `alert-rules`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/alerts` | viewer+ | List open alerts. `?include_resolved=true` for history |
| GET | `/alerts/count` | viewer+ | Returns `{ "open": N }` for sidebar badge |
| PUT | `/alerts/{id}/resolve` | editor+ | Manually resolve an alert |
| GET | `/alert-rules/{device_id}` | viewer+ | Get threshold rules for a device |
| POST | `/alert-rules/{device_id}` | editor+ | Create or update threshold rules |

---

## Frontend Changes

### Dashboard alert feed

New card in the detail row alongside Agent Status and Recent Events.

- Lists all open alerts: severity icon + alert type + device/agent name + relative time ("2 min ago")
- Empty state: green checkmark + "All clear"
- Polls `/alerts` every 30s

### Sidebar badge

- Dashboard nav item shows a red badge with open alert count when `open > 0`
- Badge disappears when count reaches 0
- Fetches from `/alerts/count` every 30s

### Toast notifications

- On each 30s poll, diff new alerts against previous fetch
- Any alert present in new fetch but absent from previous triggers a toast via existing `ToastContainer`
- Toast message: alert message string
- Toast style: error (red) for new alerts

### Threshold configuration in device form

- In `DeviceManagement.js` device edit form, add a collapsible "Alert Thresholds" section at the bottom
- Three optional number inputs: **Bandwidth In (%)**, **Bandwidth Out (%)**, **Error Rate**
- Blank field = threshold disabled for that metric
- Loaded via `GET /alert-rules/{device_id}` on form open
- Saved via `POST /alert-rules/{device_id}` on form submit (same save action as device update)

---

## Files Changed

| File | Change |
|------|--------|
| `backend/models.py` | Add `Alert` and `AlertRule` SQLAlchemy models |
| `backend/routers/alerts.py` | New router — all alert + alert-rules endpoints |
| `backend/main.py` | Register alerts router; start background evaluation task |
| `backend/alembic/versions/` | New migration for `alerts` and `alert_rules` tables |
| `frontend/src/services/api.js` | Add `getAlerts`, `getAlertCount`, `resolveAlert`, `getAlertRules`, `saveAlertRules` |
| `frontend/src/components/Dashboard.js` | Add alert feed card, sidebar badge polling |
| `frontend/src/components/Sidebar.js` | Add badge to Dashboard nav item |
| `frontend/src/components/DeviceManagement.js` | Add threshold fields to device edit form |

---

## Out of Scope

- Email or webhook delivery
- Alert severity levels (all alerts treated equally)
- Per-interface threshold configuration (per-device only)
- Alert suppression windows / maintenance mode
