# Architecture

Start with `CLAUDE.md` (services table, data flow, key constraints) and the README (features, API reference, schema). This page adds the map an agent needs to find and change code.

## Services and code locations

| Service | Directory | Entry point | Notes |
|---|---|---|---|
| nginx | `nginx/` | `nginx.conf`, `conf.d/default.conf` (`conf.d-tls/` for TLS) | the only published port (80, or 443 with `docker-compose.tls.yml`); routes `/api/*` → backend (prefix stripped), `/` → frontend; **denies `/api/internal/`**; `security_headers.inc` adds frame/nosniff/referrer headers and a report-only CSP |
| frontend | `frontend/` | `src/index.js`, `src/App.js` | React (Create React App), pre-built bundle served by Nginx |
| backend | `backend/` | `main.py` | FastAPI; routers in `backend/routers/` (agents, alerts, audit_log, auth, config, devices, fleet, internal, maintenance, metrics, notifications, prometheus, topology); background `alert_evaluator.py`; Alembic migrations in `backend/alembic/versions/` |
| manager | `manager/` | `main.py` | agent registry (`registry.py`, `routers/`), Parquet ingest into DuckDB (`db.py`, single global write lock), commands for agents |
| agent | `agent/` | `main.py` | SNMP polling (`snmp.py`), trap receiver (`trap_receiver.py`), upload buffer and disk retry queue (`uploader.py`) |
| postgres | — | TimescaleDB image | devices, users, alerts, config, audit log |
| snmp-simulator | `snmp-simulator/` | — | UDP 1161 test target for `make simulation` |

`shared/` holds code vendored byte-identically into backend, manager and agent (currently `logging_json.py`: JSON logs, correlation IDs). `scripts/` has backup/restore, key rotation, cert generation, simulation and load-test tooling. `observability/` + `docker-compose.observability.yml` add Prometheus/Grafana.

## Compose files

| File | Purpose |
|---|---|
| `docker-compose.yml` | base stack (6 services + nginx) |
| `docker-compose.override.yml` | local development overrides (applied automatically) |
| `docker-compose.prod.yml` | production hardening: Docker secrets (`*_FILE` variables), `cap_drop: [ALL]`, read-only root filesystems, limits |
| `docker-compose.tls.yml` | TLS termination at nginx (see `docs/runbooks/tls.md`) |
| `docker-compose.observability.yml` | metrics stack |

## Request paths

- **Browser → API**: `/api/<route>` at nginx → backend `/<route>` with a JWT bearer token (`POST /auth/login` issues it).
- **Manager → backend**: `GET /internal/devices-for-agent/{agent_id}` directly on the internal network with `Authorization: Bearer <MANAGER_API_KEY>`.
- **Agent → manager**: register/heartbeat/deregister and `POST /ingest` (Parquet + SHA-256) with the manager key.
- **Backend → DuckDB**: read-only mount of `data/db/metrics.db` for metrics queries, keyed by `device_ip`.

## Decisions on record

- Metrics stay in DuckDB (not TimescaleDB) — `docs/metrics-store-decision.md`, backed by `docs/scale-benchmark.md` (1000-device target, ≈5,000 rows/s).
- Single-host docker-compose is the production platform (no Kubernetes) — `docs/enterprise-readiness-roadmap.md`.
- Planned and completed work is tracked step by step in `docs/implementation-plan.md`; reference step numbers in commits and PRs as existing history does.
