# Manager Integration Design

**Date:** 2026-05-02  
**Status:** Approved

## Summary

Integrate the existing `manager/` service into the main project by transitioning from the backend's direct SNMP polling model to a distributed agent-based model. Agents collect SNMP data and upload parquet files to the manager. The backend becomes a UI API layer reading metrics from DuckDB. The frontend gains an Agents tab.

---

## Architecture

```
[Agent] ──register/heartbeat──▶ [Manager :8001]
[Agent] ──GET /config──────────▶ [Manager] ──▶ [Backend :8000 /internal/devices]
[Agent] ──POST /ingest─────────▶ [Manager] ──writes──▶ DuckDB (/data/db/metrics.db)

[Frontend :3000] ──────────────▶ [Backend :8000]
                                      │
                                      ├─ devices/agents API ──▶ Postgres
                                      └─ metrics API ──────────▶ DuckDB (read-only mount)
```

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Collection model | Agent-based (manager replaces direct polling) | Enables distributed collection |
| Backend role | Kept as UI API layer | Frontend already wired to it; clean separation of config (Postgres) vs metrics (DuckDB) |
| Device source of truth | Backend Postgres | Extend with v3 fields; avoids sync problem |
| Backend reads DuckDB | Direct file mount (read-only) | No extra HTTP hop; DuckDB safe for concurrent reads |
| Postgres metrics tables | Hard cut — dropped | In active dev, no production data to preserve |
| Manager → backend auth | None (same Docker network) | Network isolation is sufficient for co-located services |
| SNMP version support | Keep v1/2c/v3 | Too much real-world gear still on v2c |
| Parquet structure | Agents write structured parquet (interface_name, oid_name pre-parsed) | Avoids expensive OID translation at query time |
| Agent deployment | Single in compose, multi-agent ready (assigned_agent_id required) | Clean for dev, correct for distributed scaling |
| Upload trigger | Dual threshold: 60s elapsed OR 500 rows | Latency bound + memory bound |
| Upload failure | Retry with exponential backoff, discard after 1 hour | Covers transient outages without unbounded disk growth |
| Frontend agents panel | Full Agents tab | Visibility into agent health is essential for ops |

---

## Data Flow

1. Agent starts → registers with manager → receives `agent_id`
2. Agent calls `GET /config/{agent_id}` → manager calls `GET /internal/devices?agent_id=X` on backend → returns device list with v3 credentials
3. Agent polls devices via SNMP, buffers rows in memory
4. When **500 rows OR 60s** elapsed → serialize buffer to parquet → POST to `POST /ingest` with `X-SHA256` and `X-File-ID` headers
5. Manager validates checksum, deduplicates via `ingest_log`, writes to DuckDB `snmp_polls`
6. Agent sends heartbeat to manager every 30s with `pending_uploads` count
7. Backend mounts DuckDB read-only, joins `device_ip → device_id` via Postgres on metrics queries
8. On upload failure: file retained on disk at `/data/queue/`, retried with exponential backoff, discarded after 1 hour

---

## Parquet Schema (`snmp_polls`)

| Column | Type | Notes |
|---|---|---|
| `agent_id` | VARCHAR | Registered agent ID |
| `device_ip` | VARCHAR | Device IP address |
| `interface_name` | VARCHAR | e.g. `GigabitEthernet0/0` (nullable for non-interface OIDs) |
| `oid_name` | VARCHAR | Human-readable name e.g. `ifInOctets` |
| `oid` | VARCHAR | Raw OID string |
| `value` | VARCHAR | Raw string value (backend casts on read) |
| `collected_at` | TIMESTAMPTZ | When the agent collected the sample |

---

## Component Changes

### Backend

- **Add migration:** extend `devices` table with nullable v3 fields: `username`, `auth_protocol`, `auth_password`, `priv_protocol`, `priv_password`, `assigned_agent_id`
- **Add endpoint:** `GET /internal/devices?agent_id=X` — returns device list for a given agent, no auth required
- **Add endpoint:** `GET /agents` — proxies manager's `/agents` response to frontend
- **Remove:** `run_scheduled_collection` background task and `services/collector.py`
- **Add migration:** drop `snmp_metrics` and `if_mib_metrics` tables
- **Rewrite:** `routers/metrics.py` to query DuckDB directly via read-only duckdb connection; join `device_ip → device_id` using Postgres device records
- **Remove:** `services/prometheus.py` (Prometheus scraping no longer needed for collection)
- **Docker compose:** mount `./data/db:/data/db:ro`

### Manager

- **Update:** `routers/registration.py` — replace `_devices_for(agent_id)` DuckDB query with HTTP call to `http://backend:8000/internal/devices?agent_id={agent_id}`
- **Update:** `db.py` — remove `devices` table from `_SCHEMA`; extend `snmp_polls` schema with `interface_name VARCHAR` and `oid_name VARCHAR` columns to match structured parquet
- **Add:** `BACKEND_URL` env var to `config.py`
- **Docker compose:** add `BACKEND_URL=http://backend:8000` env var; add `depends_on: backend`

### Agent (new `agent/` folder)

New Python service with four concurrent loops:

| Loop | Behavior |
|---|---|
| **Register** | On startup: POST `/register`, persist `agent_id` to disk. On restart: reuse stored `agent_id` or re-register if 404 |
| **Heartbeat** | Every 30s: POST `/heartbeat` with `pending_uploads` count |
| **Poll** | Per device: SNMP walk on interval, append rows to in-memory buffer |
| **Upload** | Flush when 500 rows OR 60s elapsed: serialize to parquet, POST to `/ingest`, clear buffer |

**Retry queue:** Failed uploads written to `/data/queue/{file_id}.parquet`. Background retry loop with exponential backoff (1s → 2s → 4s … max 5min). Files older than 1 hour are discarded.

**Env vars:**

| Var | Default | Notes |
|---|---|---|
| `MANAGER_URL` | — | Required |
| `MANAGER_API_KEY` | — | Required |
| `AGENT_HOSTNAME` | system hostname | Used in registration |
| `POLL_INTERVAL_SECONDS` | `60` | How often to poll each device |
| `UPLOAD_MAX_ROWS` | `500` | Row threshold for upload |
| `UPLOAD_MAX_AGE_SECONDS` | `60` | Time threshold for upload |
| `RETRY_MAX_AGE_SECONDS` | `3600` | Discard queued files older than this |

### Frontend

- **Add:** `Agents` tab in main navigation
- **Agents page:** table showing `agent_id`, `hostname`, `ip`, status badge (online/degraded/offline), `last_seen`, `pending_uploads`, assigned device count
- **Device form:** add optional v3 credential fields (`username`, `auth_protocol`, `auth_password`, `priv_protocol`, `priv_password`) and `assigned_agent_id` dropdown (populated from agents list)
- **`services/api.js`:** add `getAgents()` call to `GET /agents`

### Docker Compose

- **Add** `agent` service: build `./agent`, env vars for `MANAGER_URL`/`MANAGER_API_KEY`/`POLL_INTERVAL_SECONDS`, volume `./data/agent-queue:/data/queue`, `depends_on: manager`
- **Update** `manager` service: add `BACKEND_URL=http://backend:8000`, add `depends_on: backend`
- **Update** `backend` service: add volume `./data/db:/data/db:ro`

---

## What Is Not Changing

- Manager's API key authentication for agents
- Manager's dead-letter mechanism for bad parquet files
- Manager's ingest deduplication via `ingest_log`
- Frontend's device CRUD flow (same backend endpoints, extended schema)
- Backend's CORS configuration
- Postgres for all device/config data
