# SNMP Metrics Collector

A distributed SNMP monitoring platform for network devices. Devices are managed via a FastAPI backend (PostgreSQL), polling is handled by autonomous agents that upload Parquet batches to a manager service (DuckDB), and a React dashboard provides visualization and administration.

## Features

- **Distributed collection**: Agents poll SNMP devices autonomously and upload batched Parquet files to the manager. The backend never touches devices directly.
- **OID configuration**: Manage a whitelist of OIDs to collect via the Configuration Manager UI.
- **Device management**: Full CRUD for network devices with SNMP v2c and v3 support. Credentials are stored separately and only accessible to editors and admins.
- **JWT authentication**: Role-based access control (admin / editor / viewer) with bcrypt password hashing. First login forces a password change.
- **Interface metrics**: Per-interface traffic rates, octets, and status visible in the Metrics view.
- **Agent visibility**: Agent registration, heartbeat status, and last-seen tracking in the Agents tab.
- **Alerting**: Automatic alert detection every 30s — device unreachable, interface down, bandwidth threshold exceeded, agent offline. Active alerts appear on the dashboard with a sidebar badge and toast notifications for new alerts.
- **Alert rules**: Per-device configurable thresholds for inbound/outbound bandwidth (%) and error rate. Set in the Device edit modal.
- **End-to-End Simulation**: Built-in SNMP simulator container for testing without real hardware.

## Architecture

Seven Docker services:

| Service | Port | Role |
|---------|------|------|
| nginx | 80 | Reverse proxy — all public traffic; `/api/internal/` blocked |
| backend | (internal) | FastAPI — auth, device CRUD, metrics API, OID config |
| postgres | (internal) | Device config, users, OID whitelist |
| manager | 8001 | Agent registry, Parquet ingest, DuckDB writes |
| frontend | (internal) | React SPA served via nginx |
| agent | — | Asyncio daemon — polls SNMP, uploads Parquet |
| snmp-simulator | 1161/udp | Simulated SNMP target for testing |

Backend and frontend have no exposed ports — all traffic goes through nginx.

### Data flow

```
Device registered in Backend (Postgres)
  → Agent registers with Manager, receives device + OID config
  → Agent polls SNMP, buffers rows, uploads Parquet → POST /ingest
  → Manager writes rows into DuckDB (data/db/metrics.db)
  → Backend mounts DuckDB read-only, serves metrics to Frontend
```

## Quick Start

**Prerequisites:** Docker 20+, Docker Compose 2+

```bash
make setup
```

This builds all containers, starts them, waits for the backend to be ready, and runs database migrations. A `.env` file is created from `.env.example` automatically.

Access the app at **http://localhost**.

On first startup, a bootstrap admin account is created:

- **Email:** `admin@localhost`
- **Password:** `changeme`

You will be prompted to set a new password on first login.

> **Before deploying to production:** set `JWT_SECRET` and `MANAGER_API_KEY` to strong random values in `.env`.

## Authentication

All API routes require a JWT bearer token except `POST /auth/login`.

### Roles

| Role | Devices | Credentials | Config | Delete devices | Register users |
|------|---------|-------------|--------|----------------|----------------|
| admin | read/write | yes | read/write | yes | yes |
| editor | read/write | yes | read/write | no | no |
| viewer | read only | no | read only | no | no |

Viewers never see SNMP credentials. The device list omits community strings and v3 fields — credentials are only returned by `GET /devices/{id}/credentials` (editor+ required).

### Creating users

Only admins can create users:

```bash
curl -X POST http://localhost/api/auth/register \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "ops@example.com", "password": "...", "role": "editor"}'
```

## Logging

All services emit JSON-structured logs:

```json
{"time": "...", "level": "INFO", "service": "backend", "message": "..."}
```

Tail logs with `make logs`, `make logs-backend`, or `make logs-manager`.

## Simulation & Testing

```bash
make simulation       # run end-to-end SNMP collection test
make clean-simulation # remove test device and simulation data
```

This starts all services including the `snmp-simulator`, adds a test device, waits for the agent to collect, and verifies metrics are stored in DuckDB.

## Configuration

### Environment variables

```bash
# Required — startup fails without these
JWT_SECRET=replace-with-a-long-random-secret
MANAGER_API_KEY=change-me-in-production

# Database
POSTGRES_DB=snmp_metrics
POSTGRES_USER=snmpuser
POSTGRES_PASSWORD=snmppass
POSTGRES_PORT=5432

# Backend
FRONTEND_URL=http://localhost   # CORS origin
JWT_EXPIRE_HOURS=8
```

Generate strong secrets:
```bash
openssl rand -hex 32   # for JWT_SECRET
openssl rand -hex 24   # for MANAGER_API_KEY
```

## Makefile commands

```bash
make setup             # First-time: build + start + migrate
make up                # Start all services
make down              # Stop all services
make build             # Rebuild containers
make reset             # clean + build + up
make migrate           # Run Alembic migrations
make test              # Run manager + backend test suites
make simulation        # End-to-end SNMP collection test
make clean-simulation  # Remove simulation test data
make status            # Show container status

make logs              # Tail all logs
make logs-backend      # Tail backend logs
make logs-frontend     # Tail frontend logs
make logs-manager      # Tail manager logs

make shell-backend     # sh into backend container
make shell-db          # psql into postgres

make dev-frontend      # Run frontend locally (npm start)
make dev-backend       # Run backend locally (uvicorn --reload)
```

## Project structure

```
snmp-collector/
├── backend/                 # FastAPI (auth, devices, metrics, OID config, internal)
│   ├── alembic/             # Database migrations
│   ├── routers/             # auth, devices, metrics, config, agents, alerts, alert-rules, internal
│   ├── alert_evaluator.py   # Background task: checks conditions, writes/resolves alerts every 30s
│   ├── tests/               # pytest suite
│   ├── auth.py              # JWT, bcrypt, role enforcement
│   └── main.py              # Bootstrap admin seed, app setup
├── manager/                 # Agent registry + Parquet ingest → DuckDB
│   ├── routers/             # registration, ingest
│   ├── tests/               # pytest suite
│   └── main.py
├── frontend/                # React SPA
│   └── src/
│       ├── components/      # DeviceManagement, ConfigurationManager, AgentsPage, ...
│       ├── pages/           # LoginPage, ChangePasswordPage
│       └── services/api.js  # Axios client with JWT interceptors
├── nginx/
│   └── conf.d/default.conf  # Proxy rules; /api/internal/ blocked from public
├── snmp-simulator/          # Net-SNMP simulator for testing
├── data/                    # Runtime: DuckDB, agent queue, agent registry
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Database schema (PostgreSQL)

| Table | Purpose |
|-------|---------|
| `users` | Accounts with bcrypt passwords, roles, and `force_password_change` flag |
| `devices` | Network devices — SNMP config, agent assignment (credentials excluded from list response) |
| `collection_configs` | OID whitelist — name, description, enabled flag |
| `alerts` | Active and resolved alerts — type, message, triggered/resolved timestamps, status |
| `alert_rules` | Per-device bandwidth and error rate thresholds used by the alert evaluator |

Metrics are stored in DuckDB (`data/db/metrics.db`) by the manager. The backend mounts this file read-only.

## Troubleshooting

**Port 5432 conflict** — a local Postgres instance is running:
```bash
brew services stop postgresql   # or equivalent for your version
```

**Backend won't start — "JWT_SECRET not set":**
```bash
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
```

**No metrics showing up:**
1. Check the agent registered: `make logs-manager`
2. Verify the device IP is reachable from the agent container
3. Check SNMP community string or v3 credentials are correct
4. Ensure UDP 161 is not firewalled

---

Built with Docker, FastAPI, React, PostgreSQL, DuckDB, and Nginx.
