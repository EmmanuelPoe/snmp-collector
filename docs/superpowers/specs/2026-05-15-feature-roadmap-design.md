# Feature Roadmap — snmp-collector

**Date:** 2026-05-15  
**Goal:** Evolve snmp-collector into a professional network monitoring product comparable to DX NetOps, focused on networking gear only.  
**Approach:** One feature at a time, in priority order. Each feature is independently shippable.

---

## Current Baseline

The core pipeline is fully operational:
- Device registration (Postgres) → Agent SNMP polling → Parquet upload → Manager DuckDB storage → Backend API → React frontend
- Interface Monitor with real-time bps rates, utilization %, sparklines, and time-range charts
- Device management CRUD, agent registry, JWT auth with RBAC (admin/editor/viewer)
- Dashboard with live stats, traffic charts, agent status

Gaps: Configuration UI incomplete, no alerting, no trap reception, limited OID coverage.

---

## Feature Backlog (Priority Order)

### Feature 1 — Configuration Manager UI
**Impact:** High | **Effort:** Low (frontend only)

Complete the half-built `ConfigurationManager.js` frontend. Wire it to existing backend endpoints:
- `GET/POST /config/configs` — OID collection config list and creation
- `GET /config/modules` — supported module list
- Add missing backend endpoints: `GET/PUT /config/modules/{name}`, `POST /config/reload`
- Add per-device poll interval field (stored on Device model or CollectionConfig)
- Enable/disable toggles per OID config row

Success: Admin can manage what OIDs are collected without touching the database or env vars.

---

### Feature 2 — User Management UI
**Impact:** Medium | **Effort:** Low (frontend only)

Admin-only page at `/admin/users` to manage the user roster:
- List all users (id, email, role, is_active, created_at)
- Create new user (email, password, role) — calls existing `POST /auth/register`
- Edit role and active status — needs `PUT /auth/users/{id}` backend endpoint
- Deactivate / reactivate (soft delete, not hard delete)

Backend: Add `GET /auth/users` and `PUT /auth/users/{id}` endpoints (admin role required).  
Frontend: New `UsersPage.js` component, nav link visible only to admins.

Success: Admins can onboard teammates and adjust permissions without CLI access.

---

### Feature 3 — Device Health Scoring
**Impact:** Medium | **Effort:** Low–Medium (computation from existing data)

Compute a 0–100 health score per device from data already in DuckDB:
- **Reachability** (40 pts): ratio of successful polls to expected polls in last hour
- **Interface errors** (30 pts): penalize high ifInErrors + ifOutErrors rates
- **Utilization** (30 pts): penalize interfaces with utilization > 80%

Implementation:
- Manager: new endpoint `GET /internal/metrics/health/{device_ip}` returning score + breakdown
- Backend: proxy `GET /metrics/health/{device_id}`
- Frontend: score badge on device cards in DeviceManagement and dashboard device list
- Dashboard: aggregate "unhealthy devices" count widget

Success: Operator can see at a glance which devices need attention without drilling into each one.

---

### Feature 4 — Availability Tracking
**Impact:** Medium | **Effort:** Medium (new DuckDB query patterns)

Derive device and interface availability from poll timestamps already in DuckDB:
- A device is "up" in an interval if at least one poll succeeded in that window
- Store nothing new — compute from gaps in `snmp_polls.collected_at`

New endpoints:
- `GET /internal/metrics/availability/{device_ip}?days=30` → `{ uptime_pct, outages: [{start, end, duration_min}], mttr_min }`
- Backend proxy: `GET /metrics/availability/{device_id}`

Frontend:
- Availability tab or section in DeviceMetrics (alongside Interface Monitor)
- 30-day timeline bar (green/red blocks per hour)
- Summary: uptime %, outage count, MTTR

Success: NOC team can report device SLA compliance from the UI.

---

### Feature 5 — Threshold Alerts
**Impact:** High | **Effort:** Medium–High (new data model + background evaluator + UI)

Define rules that trigger alerts when metrics cross thresholds:

**Data model (Postgres):**
```
AlertRule: id, name, device_id (nullable = all devices), metric (utilization|errors|reachability), operator (gt|lt), threshold, severity (critical|warning|info), enabled
Alert: id, rule_id, device_id, interface_name, value, triggered_at, resolved_at (nullable)
```

**Alert evaluator:**
- Manager background task runs every poll cycle
- Evaluates enabled rules against latest metrics in DuckDB
- Inserts new Alert records via backend API if threshold crossed
- Resolves open alerts when metric returns to normal

**Backend endpoints:**
- CRUD `GET/POST/PUT/DELETE /alerts/rules`
- `GET /alerts` (active + recent history, filterable by device/severity)

**Frontend:**
- Alert Rules page (create/edit/delete rules)
- Alert banner on Dashboard showing active critical/warning count
- Alert history table with resolve times
- Bell icon in nav with unread count badge

**Notifications (stretch):** Webhook POST on alert trigger (configurable URL per rule).

Success: Operator is notified of threshold violations without constantly watching charts.

---

### Feature 6 — SNMP Trap Receiver
**Impact:** High | **Effort:** High (new UDP listener service)

Receive async SNMP traps from devices (link-up/down, reboots, interface failures):

**Architecture:**
- New `trap-receiver` service in docker-compose (Python, port 162/udp)
- Uses `pysnmp` TrapReceiver or `snmptrapd` to parse incoming PDUs
- Writes parsed traps to manager via `POST /ingest/traps` (new endpoint)
- Manager stores traps in DuckDB `snmp_traps` table (schema already exists)

**Backend:** `GET /traps?device_id=X&hours=24` → trap event list  
**Frontend:**
- Trap event feed on Dashboard (already has event feed skeleton)
- Filter by device, trap type, severity
- Trap count badge per device in device list

Success: Link-down traps appear in the dashboard within seconds of the event occurring.

---

### Feature 7 — MIB Browser / OID Discovery
**Impact:** Medium | **Effort:** High (new SNMP walk capability)

On-demand OID discovery for a target device:

**Flow:**
1. User clicks "Discover OIDs" on a device
2. Frontend calls `POST /metrics/discover/{device_id}` 
3. Backend triggers agent (or a manager-side walk) to perform `snmpwalk`
4. Results streamed back: `{ oid, oid_name, value, type }` list
5. User checks boxes to add OIDs to collection config

**Implementation options:**
- A: Manager performs walk directly using pysnmp (simpler, no agent changes)
- B: Agent receives walk command via new manager endpoint (more consistent with architecture)

Recommended: Option A (manager walk) — faster to implement, no agent protocol changes needed.

**Frontend:** MIB browser modal on device detail, tree view of discovered OIDs, bulk-add to config.

Success: Adding a new device type's OIDs takes minutes instead of manual MIB research.

---

### Feature 8 — Network Topology Map
**Impact:** Medium | **Effort:** Very High (new OID collection + graph UI)

Visual node-link map of devices and their physical/logical neighbors:

**Prerequisites:**
- Feature 7 (MIB Browser) to discover LLDP/CDP OIDs
- Collect LLDP-MIB OIDs: `lldpRemSysName`, `lldpRemPortId`, `lldpRemManAddr`

**Implementation:**
- Agent collects LLDP neighbor data as new OID set
- Manager builds neighbor graph from DuckDB: `GET /internal/topology`
- Backend proxy: `GET /topology`
- Frontend: D3.js or vis.js force-directed graph
  - Nodes = devices (color by health score)
  - Edges = LLDP neighbors (label with interface name)
  - Click node → opens Interface Monitor for that device

Success: Operator can visually trace network paths and immediately identify which devices are neighbors of a failing node.

---

## Build Sequence Summary

| # | Feature | Effort | Prerequisite |
|---|---------|--------|--------------|
| 1 | Configuration Manager UI | Low | None |
| 2 | User Management UI | Low | None |
| 3 | Device Health Scoring | Low–Med | None |
| 4 | Availability Tracking | Med | None |
| 5 | Threshold Alerts | Med–High | None (builds on #3 data) |
| 6 | SNMP Trap Receiver | High | None |
| 7 | MIB Browser / OID Discovery | High | None |
| 8 | Network Topology Map | Very High | #7 (LLDP OID collection) |

Each feature 1–7 can be started independently. Feature 8 depends on LLDP OID collection established in Feature 7.
