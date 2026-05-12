# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make up              # Start all 6 services (copies .env.example → .env if missing)
make down            # Stop all services
make build           # Rebuild containers
make reset           # clean + build + up

make migrate         # Run alembic migrations inside backend container
make test            # Run manager pytest suite (only service with tests)
make simulation      # End-to-end SNMP collection test using the simulator
make clean-simulation # Remove simulation test data from postgres

make logs-backend    # Tail backend logs
make logs-frontend   # Tail frontend logs
make logs-manager    # Tail manager logs
make shell-backend   # sh into backend container
make shell-db        # psql into postgres (snmpuser / snmp_metrics)

# Local dev (outside Docker)
cd frontend && npm start
cd backend && uvicorn main:app --reload
```

Run a single manager test:
```bash
docker-compose exec manager pytest tests/test_ingest.py -v
```

## Architecture

Six services defined in `docker-compose.yml`:

| Service | Port | Stack | Storage |
|---------|------|-------|---------|
| frontend | 3000 | React | — |
| backend | 8000 | FastAPI + SQLAlchemy | PostgreSQL (TimescaleDB) |
| manager | 8001 | FastAPI | DuckDB (read-write) |
| agent | — | Python asyncio | disk queue (`data/agent-queue/`) |
| postgres | 5432 | TimescaleDB | `postgres_data` volume |
| snmp-simulator | 1161/udp | — | — |

### Data flow

```
Device registered in Backend (Postgres)
  → Manager fetches device list from Backend /internal/devices-for-agent/{agent_id}
  → Agent registers with Manager, receives device config
  → Agent polls SNMP, buffers rows, uploads Parquet to Manager POST /ingest
  → Manager writes Parquet rows into DuckDB snmp_polls table (data/db/metrics.db)
  → Backend reads DuckDB read-only to serve metrics to Frontend
```

### Key design constraints

- **Backend owns device config** (Postgres), but does **no SNMP polling**.
- **Manager owns DuckDB** (`data/db/metrics.db`). Backend mounts it read-only. Never open DuckDB for writing from the backend.
- **Manager has no public API docs** (`docs_url=None`). All endpoints require `Authorization: Bearer <MANAGER_API_KEY>`.
- **Agent is mostly stateless**: its only on-disk state is an agent ID file (`data/agent-id/`) and a retry queue for failed uploads (`data/agent-queue/`).
- Metrics are keyed by `device_ip` (not `device_id`). The backend resolves `device_id → ip_address` (from Postgres) before querying DuckDB.

### Backend routers

- `devices` — CRUD for `Device` model (Postgres)
- `metrics` — query `snmp_polls` in DuckDB (read-only)
- `config` — CRUD for `CollectionConfig` model (Postgres, OID whitelist)
- `agents` — proxy to manager's agent registry
- `internal` — endpoints consumed by manager (device config lookup)

### Manager routers

- `registration` — agent register/heartbeat/deregister; state persisted to `data/registry/registry.json`
- `ingest` — accepts Parquet uploads (`POST /ingest`), validates SHA-256, deduplicates, writes to DuckDB

### Agent loops (concurrent asyncio tasks)

- `_poll_loop` — fetches device list, runs SNMP walks in parallel, feeds `UploadBuffer`
- `_heartbeat_loop` — pings manager every 30s
- `_retry_loop` — retries failed uploads from disk queue every 60s

## Environment

Copy `.env.example` to `.env`. Required variables beyond defaults:
- `MANAGER_API_KEY` — shared secret between manager and agent (and backend's agent proxy calls)
- Postgres credentials: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
