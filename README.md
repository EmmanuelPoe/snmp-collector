# SNMP Metrics Collector

A distributed SNMP monitoring platform for network devices. Devices are managed via a FastAPI backend (PostgreSQL), polling is handled by autonomous agents that upload Parquet batches to a manager service (DuckDB), and a React dashboard provides visualization and administration.

## Features

- **Distributed collection** — Agents poll SNMP devices autonomously and upload batched Parquet files to the manager. The backend never touches devices directly.
- **Agent provisioning** — Admins create named agent slots from the UI, get a `docker run` one-liner with a one-time claim token, and agents register themselves on first start. No manual ID management required.
- **Device tags** — Tag devices (e.g. `datacenter-nyc`, `core-router`) and filter both the device list and dashboard traffic chart by tag.
- **Historical trend charts** — Per-interface AreaCharts with 1h / 6h / 24h / 7d time-range selector. Shows bandwidth in/out over time; a secondary error chart appears when errors are detected.
- **Interface metrics** — Per-interface traffic rates, utilization %, and error counts on the Interface Monitor page.
- **Alerting** — Automatic alert detection every 30s: device unreachable, interface down, bandwidth threshold exceeded, agent offline. Active alerts appear on the dashboard with a sidebar badge and toast notifications for new alerts.
- **Alert rules** — Per-device configurable thresholds for inbound/outbound bandwidth (%) and error rate, set in the Device edit modal.
- **OID configuration** — Manage a whitelist of OIDs to collect via the Configuration Manager.
- **Device management** — Full CRUD for network devices with SNMP v2c and v3 support. Credentials are stored separately and only accessible to editors and admins.
- **JWT authentication** — Role-based access control (admin / editor / viewer) with bcrypt password hashing. First login forces a password change.
- **End-to-end simulation** — Built-in SNMP simulator container for testing without real hardware.

## Architecture

Seven Docker services:

| Service | Port | Role |
|---------|------|------|
| nginx | 80 | Reverse proxy — all public traffic; `/api/internal/` blocked |
| backend | (internal) | FastAPI — auth, device CRUD, metrics API, OID config, alert evaluator |
| postgres | (internal) | Device config, users, OID whitelist, alerts |
| manager | 8001 | Agent registry, slot provisioning, Parquet ingest, DuckDB writes |
| frontend | (internal) | React SPA served via nginx |
| agent | — | Asyncio daemon — polls SNMP, uploads Parquet |
| snmp-simulator | 1161/udp | Simulated SNMP target for testing |

Backend and frontend have no exposed ports — all traffic goes through nginx.

### Data flow

```
Admin creates agent slot in UI → gets docker run one-liner with CLAIM_TOKEN
  → Agent starts, calls POST /claim → receives stable agent_id → saves to disk
  → Agent fetches device list from Manager, polls SNMP in parallel
  → Agent buffers rows, uploads Parquet → POST /ingest
  → Manager deduplicates and writes rows into DuckDB (data/db/metrics.db)
  → Backend mounts DuckDB read-only, serves metrics to Frontend
  → Alert evaluator runs every 30s, writes/resolves alerts in Postgres
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

## Using the UI

### Dashboard

The dashboard gives a live overview — device count, agent health, active alerts, and a per-device traffic chart. Use the **tag filter** dropdown to scope the traffic chart to a subset of devices. The dashboard auto-refreshes every 30s.

### Deploying an Agent

1. Go to **Agents** in the sidebar.
2. Click **Deploy Agent**.
3. Enter a label (e.g. `NYC datacenter`).
4. Copy the generated `docker run` command and run it on the target machine.

The agent will appear as **pending** in the list until it comes online and claims its slot. Pending slots expire after 24 hours. Use **Revoke** to cancel an unclaimed slot.

To clear stale offline agents from a previous run, click **Clear Offline** on the Agents page.

### Managing Devices

1. Go to **Devices** in the sidebar.
2. Click **+ Add Device** and fill in the device name, IP, SNMP version, and credentials.
3. Assign an agent from the dropdown. Only online agents are shown first.
4. Optionally add **tags** (comma-separated or press Enter). Tags appear as chips in the device list and can be used to filter the view.
5. Set optional **alert thresholds** — bandwidth in/out (%) and error rate (errors/min).

Tags are normalized to lowercase with hyphens (e.g. `NYC Router` → `nyc-router`). Existing tags appear as clickable suggestions in the form.

### Interface Monitor

Go to **Metrics** in the sidebar, select a device, and all its interfaces appear as cards. Each card shows:

- Current in/out bandwidth and utilization
- Error count (highlighted red if non-zero)
- A **trend chart** with 1h / 6h / 24h / 7d time-range buttons

Clicking a card opens a detail panel on the right with a full-width chart, interface alias, and speed.

### Alerts

Active alerts appear in the dashboard alert feed and trigger toast notifications when new ones fire. The sidebar badge shows the count of open alerts. Alerts auto-resolve when the condition clears. You can also manually resolve an alert from the Alerts page.

### Configuration Manager

Manage the OID collection whitelist under **Config**. OIDs can be enabled or disabled without removing them. The agent only collects OIDs present in this list.

## Authentication

All API routes require a JWT bearer token except `POST /auth/login`.

### Roles

| Role | Devices | Credentials | Config | Delete | Users | Agent slots |
|------|---------|-------------|--------|--------|-------|-------------|
| admin | read/write | yes | read/write | yes | yes | yes |
| editor | read/write | yes | read/write | no | no | no |
| viewer | read only | no | read only | no | no | no |

Viewers never see SNMP credentials. The device list omits community strings and v3 fields — credentials are only returned by `GET /devices/{id}/credentials` (editor+ required). Agent slot creation and deletion requires admin.

### Creating users

Only admins can create users:

```bash
curl -X POST http://localhost/api/auth/register \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "ops@example.com", "password": "...", "role": "editor"}'
```

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

# Manager
MANAGER_PUBLIC_URL=http://your-host:8001  # used in generated docker run one-liners
SLOT_EXPIRY_HOURS=24                      # how long unclaimed agent tokens are valid
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

## API reference

All routes are prefixed with `/api/` through nginx (e.g. `http://localhost/api/devices`).

### Devices

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/devices` | any | List devices. `?tag=<tag>` filters by tag; `?enabled_only=true` returns only enabled devices |
| POST | `/devices` | editor+ | Create device |
| PUT | `/devices/{id}` | editor+ | Update device (partial) |
| DELETE | `/devices/{id}` | admin | Delete device |
| GET | `/devices/{id}/credentials` | editor+ | Return SNMP credentials |
| GET | `/devices/tags` | any | Return sorted list of all tags in use |

### Metrics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/metrics/rates/{device_id}` | any | Current per-interface rates and sparkline data. `?hours=1` |
| GET | `/metrics/history/{device_id}` | any | Time-bucketed bandwidth series for one interface. `?interface_name=eth0&hours=1&buckets=60` |
| GET | `/metrics/available/{device_id}` | any | List interfaces and OIDs collected for a device |
| GET | `/metrics/latest/{device_id}` | any | Raw recent poll rows |

### Agents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/agents` | any | List agents (online, offline, and pending slots) |
| POST | `/agents/slots` | admin | Create agent slot — returns token and `docker run` command |
| DELETE | `/agents/slots/{slot_id}` | admin | Revoke unclaimed slot |
| DELETE | `/agents` | admin | Remove all offline agents from the registry |

### Alerts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/alerts` | any | List alerts. `?include_resolved=true` includes resolved ones |
| GET | `/alerts/count` | any | `{"open": N}` — used for sidebar badge |
| PUT | `/alerts/{id}/resolve` | editor+ | Manually resolve an alert |
| GET | `/alert-rules/{device_id}` | any | Get alert thresholds for a device |
| POST | `/alert-rules/{device_id}` | editor+ | Upsert alert thresholds |

## Project structure

```
snmp-collector/
├── backend/
│   ├── alembic/versions/        # Migrations 001–011
│   ├── routers/
│   │   ├── auth.py              # Login, register, change-password
│   │   ├── devices.py           # CRUD + /tags endpoint + JSONB tag filter
│   │   ├── metrics.py           # Proxy to manager: rates, history, available
│   │   ├── agents.py            # Proxy to manager: list, slots, clear-offline
│   │   ├── alerts.py            # Alerts + alert-rules
│   │   ├── config.py            # OID collection config
│   │   └── internal.py          # Device config endpoint consumed by manager
│   ├── alert_evaluator.py       # Background task: evaluates conditions every 30s
│   ├── auth.py                  # JWT creation/validation, role enforcement
│   └── main.py                  # App setup, bootstrap admin seed
├── manager/
│   ├── routers/
│   │   ├── registration.py      # register, heartbeat, deregister, /claim, agent list
│   │   ├── slots.py             # POST /slots, DELETE /slots/{id}
│   │   ├── ingest.py            # POST /ingest (Parquet upload with SHA-256 check)
│   │   └── metrics.py           # /rates, /history, /available, raw query
│   ├── slots.py                 # SlotStore — token lifecycle, expiry, persistence
│   ├── registry.py              # AgentRegistry — heartbeat tracking, status
│   └── tests/                   # 65 pytest tests
├── agent/
│   ├── main.py                  # Poll loop, heartbeat loop, retry loop, claim flow
│   └── config.py                # Settings (CLAIM_TOKEN, MANAGER_URL, etc.)
├── frontend/src/
│   ├── components/
│   │   ├── Dashboard.js         # Stats, traffic chart, alerts, agent status + tag filter
│   │   ├── DeviceManagement.js  # Device CRUD modal with tags + tag filter dropdown
│   │   ├── DeviceMetrics.js     # Interface Monitor page
│   │   ├── InterfaceCard.js     # Per-interface card with trend chart
│   │   ├── InterfaceChart.js    # AreaChart with 1h/6h/24h/7d time-range selector
│   │   ├── InterfacePanel.js    # Detail sidebar with full-width chart
│   │   ├── AgentsPage.js        # Agent list, Deploy Agent modal, Clear Offline
│   │   └── ConfigurationManager.js
│   └── services/api.js          # Axios client with JWT interceptors
├── nginx/conf.d/default.conf    # Proxy rules; /api/internal/ blocked
├── snmp-simulator/
├── data/                        # Runtime: DuckDB, agent queue, registry, slots
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Database schema

### PostgreSQL (backend)

| Table | Purpose |
|-------|---------|
| `users` | Accounts with bcrypt passwords, roles, `force_password_change` flag |
| `devices` | Network devices — SNMP config, agent assignment, tags (JSON array) |
| `collection_configs` | OID whitelist — name, description, enabled flag |
| `alerts` | Active and resolved alerts — type, message, timestamps, status |
| `alert_rules` | Per-device bandwidth and error rate thresholds |

### DuckDB (manager — `data/db/metrics.db`)

| Table | Purpose |
|-------|---------|
| `snmp_polls` | All SNMP poll rows — agent_id, device_ip, interface_name, oid_name, value, collected_at |
| `ingest_log` | Deduplication log — one row per ingested Parquet file |

### File-based (manager — `data/registry/`)

| File | Purpose |
|------|---------|
| `registry.json` | Live agent registry — last_seen, hostname, status |
| `slots.json` | Pending claim slots — token, label, expiry |

## Troubleshooting

**Port 5432 conflict** — a local Postgres instance is running:
```bash
brew services stop postgresql   # or the version-specific variant
```

**Backend won't start — "JWT_SECRET not set":**
```bash
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
```

**Agent appears offline after restart:**
The agent persists its ID in `data/agent-id/`. If this volume is missing, the agent generates a new ID and the old one remains in the registry as offline. Use **Clear Offline** on the Agents page to remove stale entries.

**No metrics showing up:**
1. Confirm the agent registered: `make logs-manager`
2. Verify the device IP is reachable from the agent container
3. Check SNMP community string or v3 credentials
4. Ensure UDP 161 is not firewalled between the agent and the device

**History chart shows no data:**
The history endpoint requires at least two poll samples within the requested time window to compute a rate delta. Wait one full poll cycle (60s) after the agent starts, then try the 1h range.

---

Built with Docker, FastAPI, React, PostgreSQL (TimescaleDB), DuckDB, and Nginx.
