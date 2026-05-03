# Requirements — Manager Integration

## v1 Requirements

### Backend

- [ ] **BE-01**: Backend migration adds nullable v3 fields (`username`, `auth_protocol`, `auth_password`, `priv_protocol`, `priv_password`, `assigned_agent_id`) to `devices` table
- [ ] **BE-02**: Backend exposes `GET /internal/devices?agent_id=X` returning device list for a given agent (no auth required)
- [ ] **BE-03**: Backend exposes `GET /agents` that proxies manager's `/agents` response to the frontend
- [ ] **BE-04**: Backend `routers/metrics.py` rewritten to query DuckDB directly via read-only connection, joining `device_ip → device_id` via Postgres
- [ ] **BE-05**: Backend `run_scheduled_collection` background task and `services/collector.py` removed
- [ ] **BE-06**: Backend migration drops `snmp_metrics` and `if_mib_metrics` Postgres tables
- [ ] **BE-07**: Backend `services/prometheus.py` removed
- [ ] **BE-08**: Backend Docker Compose entry mounts `./data/db:/data/db:ro`

### Manager

- [ ] **MG-01**: Manager `routers/registration.py` `_devices_for(agent_id)` replaced with HTTP call to `http://backend:8000/internal/devices?agent_id={agent_id}`
- [ ] **MG-02**: Manager `db.py` removes `devices` table from `_SCHEMA`; extends `snmp_polls` with `interface_name VARCHAR` and `oid_name VARCHAR`
- [ ] **MG-03**: Manager `config.py` adds `BACKEND_URL` env var
- [ ] **MG-04**: Manager Docker Compose entry adds `BACKEND_URL=http://backend:8000` and `depends_on: backend`

### Agent

- [ ] **AG-01**: New `agent/` folder with Python service implementing register, heartbeat, poll, and upload loops
- [ ] **AG-02**: Agent registers on startup (POST `/register`), persists `agent_id` to disk, reuses on restart
- [ ] **AG-03**: Agent sends heartbeat every 30s (POST `/heartbeat`) with `pending_uploads` count
- [ ] **AG-04**: Agent polls each assigned device via SNMP on configurable interval, appends structured rows (with `interface_name`, `oid_name`) to in-memory buffer
- [ ] **AG-05**: Agent flushes buffer when 500 rows OR 60s elapsed: serializes to parquet, POSTs to `/ingest`
- [ ] **AG-06**: Agent retry queue: failed uploads written to `/data/queue/{file_id}.parquet`, retried with exponential backoff (1s→5min max), discarded after 1 hour
- [ ] **AG-07**: Agent supports SNMP v1, v2c, v3 (v3 uses `username`, `auth_protocol`, `auth_password`, `priv_protocol`, `priv_password`)
- [ ] **AG-08**: Agent configurable via env vars: `MANAGER_URL`, `MANAGER_API_KEY`, `AGENT_HOSTNAME`, `POLL_INTERVAL_SECONDS`, `UPLOAD_MAX_ROWS`, `UPLOAD_MAX_AGE_SECONDS`, `RETRY_MAX_AGE_SECONDS`

### Frontend

- [ ] **FE-01**: Frontend `Agents` tab added to main navigation
- [ ] **FE-02**: Agents page shows table with `agent_id`, `hostname`, `ip`, status badge (online/degraded/offline), `last_seen`, `pending_uploads`, assigned device count
- [ ] **FE-03**: Device form extended with optional v3 credential fields and `assigned_agent_id` dropdown populated from agents list
- [ ] **FE-04**: `services/api.js` adds `getAgents()` calling `GET /agents`

### Docker Compose

- [ ] **DC-01**: New `agent` service added: build `./agent`, env vars for `MANAGER_URL`/`MANAGER_API_KEY`/`POLL_INTERVAL_SECONDS`, volume `./data/agent-queue:/data/queue`, `depends_on: manager`

## Out of Scope

- Multi-region or multi-agent orchestration — not needed for initial integration
- Agent-to-manager mutual TLS — network isolation is sufficient
- Preserving snmp_metrics/if_mib_metrics Postgres data — active dev, no prod data
- Prometheus collection scraping — replaced by agent model

## Traceability

| Phase | Requirements |
|-------|-------------|
| 1 — Backend Foundation | BE-01 through BE-08 |
| 2 — Manager Updates | MG-01 through MG-04 |
| 3 — Agent Service | AG-01 through AG-08 |
| 4 — Frontend | FE-01 through FE-04 |
| 5 — Compose & Integration | DC-01 |
