# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make up              # Start all 6 services (copies .env.example → .env if missing)
make down            # Stop all services
make build           # Rebuild containers
make reset           # clean + build + up

make migrate         # Run alembic migrations inside backend container
make test            # Run the manager pytest suite in its container (other suites: see docs/testing.md)
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

Every service has tests, and CI (`.github/workflows/ci.yml`) runs all of them plus lint, secret scan, dependency audit, image build and a Playwright + simulator end-to-end job. Run the same checks locally before pushing — see [docs/testing.md](docs/testing.md):
```bash
ruff check . && ruff format --check . && python scripts/check_shared.py
(cd backend && python -m pytest -q)      # SQLite, no containers needed
(cd agent && python -m pytest -q)
npm run test:ci --prefix frontend
```

## Agent docs

- [docs/architecture.md](docs/architecture.md) — services, ownership boundaries, data flow, where code lives
- [docs/security.md](docs/security.md) — auth/RBAC, secrets, encryption, hardening, rules for changes
- [docs/ui.md](docs/ui.md) — React app structure, navigation, theming, polling
- [docs/testing.md](docs/testing.md) — every test suite, how to run it, what CI enforces
- [docs/agent-guide.md](docs/agent-guide.md) — recipes and pitfalls for common changes
- Existing planning/ops docs: [enterprise-readiness-roadmap.md](docs/enterprise-readiness-roadmap.md), [implementation-plan.md](docs/implementation-plan.md), [metrics-store-decision.md](docs/metrics-store-decision.md), [scale-benchmark.md](docs/scale-benchmark.md), [runbooks/](docs/runbooks/)

## Rules for agents

- Respect ownership: backend owns Postgres (via Alembic migrations), manager owns DuckDB writes. Never write DuckDB from the backend.
- Every new backend route needs an auth dependency (`get_current_user` or `require_role(...)`); `/internal/*` routes use `require_manager_key` and are blocked at nginx.
- Never return or log SNMP credentials outside `GET /devices/{id}/credentials`; they are encrypted at rest with `EncryptedString`.
- Edit `shared/` first, then run `python scripts/sync_shared.py`; never edit the vendored copies directly.
- Keep the `duckdb` pin identical in `manager/requirements.txt` and `backend/requirements.txt`.
- Schema changes are new Alembic revisions after the latest in `backend/alembic/versions/`.

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
- **The `duckdb` pin must move in lockstep** across `manager/requirements.txt` and `backend/requirements.txt`. One process writes that file and the other reads it, so a version skew risks a storage-format mismatch that only shows up at runtime — unit tests pass either way. Dependabot watches the two directories separately and will propose one-sided bumps (it did in #30); bump both in a single PR or not at all.
- **Manager has no public API docs** (`docs_url=None`). All endpoints require `Authorization: Bearer <MANAGER_API_KEY>`.
- **Agent is mostly stateless**: its only on-disk state is an agent ID file (`data/agent-id/`) and a retry queue for failed uploads (`data/agent-queue/`).
- Metrics are keyed by `device_ip` (not `device_id`). The backend resolves `device_id → ip_address` (from Postgres) before querying DuckDB.

### Backend routers

- `devices` — CRUD for `Device` model (Postgres)
- `metrics` — query `snmp_polls` in DuckDB (read-only)
- `config` — CRUD for `CollectionConfig` model (Postgres, OID whitelist)
- `agents` — proxy to manager's agent registry
- `internal` — endpoints consumed by manager (device config lookup)
- `alerts` — CRUD for `Alert` model; GET list, GET count, PUT resolve (Postgres)
- `fleet` — `/fleet/summary` (device/alert/agent roll-up) and `/fleet/traffic` (proxies manager's aggregate fleet-traffic query)
- `alert-rules` — per-device bandwidth/error thresholds; GET and POST upsert (Postgres)

### Manager routers

- `registration` — agent register/heartbeat/deregister; state persisted to `data/registry/registry.json`
- `ingest` — accepts Parquet uploads (`POST /ingest`), validates SHA-256, deduplicates, writes to DuckDB

### Background tasks (backend)

- `alert_evaluator.py` — runs every 30s via asyncio task started in FastAPI lifespan; checks device reachability, interface status, bandwidth thresholds, and agent heartbeats; writes/resolves `Alert` rows in Postgres

### Agent loops (concurrent asyncio tasks)

- `_poll_loop` — fetches device list, runs SNMP walks in parallel, feeds `UploadBuffer`
- `_heartbeat_loop` — pings manager every 30s
- `_retry_loop` — retries failed uploads from disk queue every 60s

## Frontend notes

- The frontend container serves a **pre-built static bundle** via Nginx. Source changes require `docker-compose build frontend && docker-compose up -d frontend` — `npm start` hot-reload only works outside Docker.
- Dashboard, sidebar badge and alert feed poll through `usePolledResource` (one request per key, paused on hidden tabs, backs off on errors): `/fleet/summary` and `/alerts` every 30s, `/fleet/traffic` every 60s. Lists are paginated server-side (`X-Total-Count`); `getDevices()` pages through the whole fleet.
- Per-device alert thresholds are configured in the Device edit modal (bandwidth in/out %, error rate).

## Environment

Copy `.env.example` to `.env`. Required variables beyond defaults:
- `MANAGER_API_KEY` — shared secret between manager and agent (and backend's agent proxy calls)
- Postgres credentials: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

## Operational notes

- **Agent identity persists** in `data/agent-id/` (`AGENT_ID_PATH`). If that volume is lost, the agent registers with a new ID and the old one shows as offline; remove it with **Clear Offline** on the Agents page.
- **Virtual interfaces are ignored by alerting**: `alert_evaluator.py` skips interfaces whose names start with `erspan`, `gre`, `sit`, `tunl`, `ip6tnl`, `bond` or `lo` (`_VIRTUAL_IFACE_PREFIXES`). Extend that tuple rather than adding special cases.
- **Trap community**: `TRAP_COMMUNITY` defaults to `public` for the simulator; the agent logs a warning at startup when a well-known community is used.
