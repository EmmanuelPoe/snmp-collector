# Roadmap — Manager Integration

**5 phases** | **21 requirements mapped** | All v1 requirements covered ✓

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 1 | Backend Foundation | Backend ready to serve agent config and read metrics from DuckDB | BE-01–BE-08 | Not Started |
| 2 | Manager Updates | Manager fetches device config from backend instead of own DuckDB | MG-01–MG-04 | Not Started |
| 3 | Agent Service | Working SNMP collection agent with retry queue | AG-01–AG-08 | Not Started |
| 4 | Frontend | Agents tab + v3 device form fields visible and functional | FE-01–FE-04 | Not Started |
| 5 | Compose & Integration | All services wire up and data flows end-to-end | DC-01 + integration | Not Started |

---

## Phase 1 — Backend Foundation

**Goal:** Backend has all migrations applied, direct SNMP polling removed, new internal endpoints live, and metrics queries reading from DuckDB.

**Requirements:** BE-01, BE-02, BE-03, BE-04, BE-05, BE-06, BE-07, BE-08

**Plans:**
- 1.1 — Database migrations (add v3 fields, drop metrics tables)
- 1.2 — Remove collector + Prometheus, add internal endpoints
- 1.3 — Rewrite metrics router to read DuckDB

**Success criteria:**
1. `GET /internal/devices?agent_id=X` returns device list from Postgres
2. `GET /agents` proxies manager response
3. `GET /metrics` queries DuckDB (not Postgres)
4. No `services/collector.py` or `services/prometheus.py` in codebase
5. Alembic migrations apply cleanly from scratch

---

## Phase 2 — Manager Updates

**Goal:** Manager no longer maintains its own devices table; fetches config from backend.

**Requirements:** MG-01, MG-02, MG-03, MG-04

**Plans:**
- 2.1 — Update registration router and db schema

**Success criteria:**
1. `GET /config/{agent_id}` on manager returns data sourced from backend
2. Manager DuckDB schema has no `devices` table
3. `snmp_polls` table has `interface_name` and `oid_name` columns

---

## Phase 3 — Agent Service

**Goal:** Functional SNMP agent that polls devices, uploads parquet to manager, and retries failed uploads.

**Requirements:** AG-01, AG-02, AG-03, AG-04, AG-05, AG-06, AG-07, AG-08

**Plans:**
- 3.1 — Agent scaffold: registration, heartbeat, config fetch
- 3.2 — Poll loop + parquet serialization + upload
- 3.3 — Retry queue

**Success criteria:**
1. Agent registers with manager on startup, reuses agent_id on restart
2. Agent sends heartbeat every 30s
3. Agent polls a v2c device and uploads parquet within 60s
4. Failed upload written to /data/queue/ and retried
5. Files older than 1 hour discarded from queue

---

## Phase 4 — Frontend

**Goal:** Operators can see agent health and assign devices to agents.

**Requirements:** FE-01, FE-02, FE-03, FE-04

**Plans:**
- 4.1 — Agents tab + API integration
- 4.2 — Device form v3 fields + agent assignment

**Success criteria:**
1. Agents tab visible in navigation
2. Agents table shows status badge (online/degraded/offline)
3. Device form shows v3 fields (collapsed or optional)
4. Device form `assigned_agent_id` dropdown populated from live agent list

---

## Phase 5 — Compose & Integration

**Goal:** Full stack runs end-to-end via `docker compose up`.

**Requirements:** DC-01

**Plans:**
- 5.1 — Docker Compose wiring + smoke test

**Success criteria:**
1. `docker compose up` starts all services without error
2. Agent registers with manager visible in Agents tab
3. Agent polls snmp-simulator devices; metrics appear in frontend
4. Retry queue volume mount persists across container restart
