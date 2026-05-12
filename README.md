# SNMP Metrics Collector

A distributed SNMP metrics collection system using Docker containers. Devices are managed centrally via a FastAPI backend (PostgreSQL), SNMP polling is coordinated by a dedicated manager service (DuckDB), and a React dashboard provides visualization and administration.

## Features

- **Multi-Module Collection**: Support for multiple SNMP modules per device (if_mib, host_resources, etc.)
- **Modular Storage Architecture**: Hybrid storage using dedicated optimized wide tables for high-volume modules (like `if_mib_metrics`) and generic EAV fallback for others.
- **Dynamic Configuration**: Manage SNMP modules and collection schedules for all devices from a centralized dashboard.
- **Device Management**: Add, edit, and manage network devices with support for custom OID modules.
- **Time-Series Storage**: PostgreSQL with TimescaleDB for efficient metric storage
- **Collection Scheduling**: Configurable collection intervals with a clear overview of polling status across all devices.
- **JWT Authentication**: Role-based access control (admin / editor / viewer) with bcrypt password hashing.
- **Modern UI**: Enterprise dark-mode interface with a collapsible sidebar, Recharts-powered dashboard (traffic trends, agent status cards, live events feed), toast notifications, and searchable/sortable tables on device and agent views.
- **Observability**: Prometheus metrics, structured JSON logging, Grafana dashboards, and Loki log aggregation.
- **End-to-End Simulation**: Built-in test workflow with a simulated SNMP agent

## Architecture

The system consists of 7 Docker containers:

1. **Nginx**: Reverse proxy — routes all public traffic on port 80; terminates HTTP for backend and frontend.
2. **PostgreSQL + TimescaleDB**: Device config, user accounts, and time-series metrics.
3. **FastAPI Backend**: API server, auth, device/config management. Not publicly exposed — served via nginx at `/api/`.
4. **Manager**: SNMP polling coordinator — stores metrics in DuckDB, manages agent registration and device config distribution.
5. **React Frontend**: Production-built static UI served through nginx.
6. **Agent**: Asyncio polling daemon — registers with manager, polls SNMP devices, uploads Parquet batches.
7. **SNMP Simulator**: Built-in simulator for testing and validation.

### Data flow

```
Device registered in Backend (Postgres)
  → Manager fetches device list from Backend /internal/devices-for-agent/{agent_id}
  → Agent registers with Manager, receives device config
  → Agent polls SNMP, buffers rows, uploads Parquet to Manager POST /ingest
  → Manager writes Parquet rows into DuckDB snmp_polls table (data/db/metrics.db)
  → Backend reads DuckDB read-only to serve metrics to Frontend
```

### Public ports

| Port | Service | Notes |
|------|---------|-------|
| `80` | Nginx | All app traffic — frontend + `/api/` proxy to backend |
| `8001` | Manager | Agent communication only; firewall to agent IPs in production |
| `5432` | Postgres | Internal only; firewall in production |

Backend and frontend containers have no exposed ports — traffic reaches them only through nginx.

## Quick Start

### Prerequisites

- Docker (version 20.x or higher)
- Docker Compose (version 2.x or higher)
- Make (optional, for convenient commands)

### Installation

1. **Clone the repository**
   ```bash
   cd snmp-collector
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env — set JWT_SECRET and MANAGER_API_KEY to strong random values
   ```

3. **Build and start the application**
   ```bash
   make build
   make up
   ```

   Or without Make:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
   make migrate
   ```

5. **Access the application**
   - Application: http://localhost (login with `admin@localhost` / `admin`)
   - API Documentation: http://localhost/api/docs
   - Manager API: http://localhost:8001

   **Change the default admin password immediately after first login** — see [Authentication](#authentication).

## Authentication

The backend uses JWT authentication. All API routes require a valid bearer token except `POST /api/auth/login`.

### Default admin account

On first startup, if the users table is empty, a seed account is created:

| Field | Value |
|-------|-------|
| Email | `admin@localhost` |
| Password | `admin` |
| Role | `admin` |

A warning is logged at startup while default credentials are active. Change the password via the API or create a new admin and delete this account.

### Roles

| Role | Devices | Config | Delete | Register users |
|------|---------|--------|--------|----------------|
| admin | read/write | read/write | yes | yes |
| editor | read/write | read/write | no | no |
| viewer | read only | read only | no | no |

### Creating users

Only admins can create users. Use the API directly:

```bash
curl -X POST http://localhost/api/auth/register \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "...", "role": "editor"}'
```

## Observability

The observability stack (Prometheus, Grafana, Loki, Promtail) runs as a separate Docker Compose overlay.

### Start with observability

```bash
make up-full     # core stack + observability
make down-full   # stop both
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| Grafana | 3001 | Dashboards (pre-provisioned SNMP collection dashboard) |
| Prometheus | 9090 (internal) | Scrapes backend and manager `/metrics` every 15s |
| Loki | internal | Log aggregation backend |
| Promtail | — | Ships container logs to Loki; parses JSON log fields |

Grafana credentials are set via `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` in `.env`.

### Structured logging

All services (backend, manager, agent) emit JSON-structured logs:

```json
{ "time": "...", "level": "INFO", "service": "backend", "message": "...", "router": "devices" }
```

Promtail parses these fields as Loki labels, making logs filterable by `service` and `level` in Grafana.

## Simulation & Testing

The project includes an automated end-to-end simulation workflow to verify the system without needing real hardware.

```bash
make simulation       # run end-to-end simulation test
make clean-simulation # remove test device and simulation data
```

**What this does:**
1. Starts all services, including a dedicated `snmp-simulator` container.
2. Runs database migrations.
3. Automatically adds a test device ("Test-Simulator") via the API.
4. Triggers an immediate SNMP collection.
5. Verifies that metrics (Interface Status, In/Out Octets, Packets) are physically stored in the database.
6. Reports the number of interfaces found and metrics collected.

## Configuration

### Environment Variables

```bash
# Database
POSTGRES_DB=snmp_metrics
POSTGRES_USER=snmpuser
POSTGRES_PASSWORD=snmppass
POSTGRES_PORT=5432

# Backend
FRONTEND_URL=http://localhost          # used for CORS origin
JWT_SECRET=replace-with-long-random-secret  # required — startup fails without this
JWT_EXPIRE_HOURS=8

# Manager
MANAGER_API_KEY=change-me-in-production    # shared secret between manager, backend, and agent

# Observability (required when using docker-compose.observability.yml)
GF_SECURITY_ADMIN_PASSWORD=replace-with-secure-grafana-password
```

## Makefile Commands

```bash
make build             # Build all Docker containers
make up                # Start core stack
make down              # Stop core stack
make up-full           # Start core stack + observability
make down-full         # Stop core stack + observability
make reset             # Full reset (clean + rebuild + start)
make migrate           # Run database migrations
make test              # Run manager test suite
make simulation        # Run end-to-end simulation test
make clean-simulation  # Remove simulation data
make status            # Show container status

make logs              # Tail all container logs
make logs-backend      # Tail backend logs
make logs-frontend     # Tail frontend logs
make logs-manager      # Tail manager logs
make logs-grafana      # Tail Grafana logs
make logs-loki         # Tail Loki logs
make logs-promtail     # Tail Promtail logs

make shell-backend     # sh into backend container
make shell-db          # psql into postgres (snmpuser / snmp_metrics)

make dev-frontend      # Run frontend locally (npm start)
make dev-backend       # Run backend locally (uvicorn --reload)
```

## Project Structure

```
snmp-collector/
├── backend/                 # FastAPI application (auth, device registry, metrics API)
│   ├── alembic/            # Database migrations
│   ├── routers/            # API endpoints (auth, devices, metrics, config, agents, internal)
│   ├── auth.py             # JWT dependency and role enforcement
│   └── main.py             # Application entry
├── manager/                 # SNMP polling coordinator (DuckDB, agent registry)
│   ├── routers/            # API endpoints (ingest, registration)
│   └── main.py             # Application entry
├── frontend/               # React application (production multi-stage build)
│   └── src/               # Source code
├── nginx/                  # Reverse proxy config
│   ├── nginx.conf
│   └── conf.d/default.conf
├── observability/          # Observability stack configs
│   ├── prometheus/         # Scrape config
│   ├── grafana/            # Datasource + dashboard provisioning
│   ├── loki/               # Loki config
│   └── promtail/           # Promtail config
├── snmp-simulator/         # Simulation container (net-snmp)
├── data/                   # Runtime data (DuckDB, dead-letter queue, registry)
├── docker-compose.yml               # Core stack
├── docker-compose.observability.yml # Observability overlay
├── Makefile
└── README.md
```

## Database Schema

The PostgreSQL database uses TimescaleDB and a modular schema:

- **users**: User accounts with bcrypt passwords and role assignments.
- **devices**: Network device information with linked SNMP modules.
- **if_mib_metrics**: Optimized wide table for interface statistics (high performance).
- **snmp_metrics**: Generic time-series storage for other modules (fallback).
- **collection_schedules**: Per-device collection timing and status.

The manager service maintains a separate DuckDB database (`data/db/metrics.db`) for SNMP poll results.

## Troubleshooting

### Database connection failed: "FATAL: role 'snmpuser' does not exist"

**Cause:** A local PostgreSQL instance is running on port 5432, conflicting with the Docker container.

**Solution:**
1. Stop local Postgres: `brew services stop postgresql` or `pkill -f postgres`
2. OR change the Docker port in `.env`: `POSTGRES_PORT=5433` then `make down && make up`

### Application won't start

```bash
make logs   # check logs for errors
make clean  # clean up
make build  # rebuild
make up     # start again
```

### Backend fails to start with "JWT_SECRET not set"

`JWT_SECRET` is required. Set it in `.env`:
```bash
JWT_SECRET=$(openssl rand -hex 32)
```

### SNMP collection not working

1. Verify device IP is reachable from the agent container
2. Check SNMP community string or v3 credentials are correct
3. Ensure UDP port 161 is not blocked by firewall
4. View agent/manager logs: `make logs-manager`

---

Built with Docker, FastAPI, React, PostgreSQL, TimescaleDB, DuckDB, Nginx, Prometheus, Grafana, and Loki.
