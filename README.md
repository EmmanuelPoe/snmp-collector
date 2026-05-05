# SNMP Metrics Collector

A distributed SNMP metrics collection system using Docker containers. Devices are managed centrally via a FastAPI backend (PostgreSQL), SNMP polling is coordinated by a dedicated manager service (DuckDB), and a React dashboard provides visualization and administration.

## Features

- **Multi-Module Collection**: Support for multiple SNMP modules per device (if_mib, host_resources, etc.)
- **Modular Storage Architecture**: Hybrid storage using dedicated optimized wide tables for high-volume modules (like `if_mib_metrics`) and generic EAV fallback for others.
- **Dynamic Configuration**: Manage SNMP modules and collection schedules for all devices from a centralized dashboard.
- **Device Management**: Add, edit, and manage network devices with support for custom OID modules.
- **Time-Series Storage**: PostgreSQL with TimescaleDB for efficient metric storage
- **Collection Scheduling**: Configurable collection intervals with a clear overview of polling status across all devices.
- **Modern UI**: Dark-mode interface with hierarchical metric selection (Device -> Module -> Metric) and real-time visualization.
- **End-to-End Simulation**: Built-in test workflow with a simulated SNMP agent

## Architecture

The system consists of 6 Docker containers:

1. **PostgreSQL + TimescaleDB**: Optimized time-series database with custom schemas for performance.
2. **Prometheus SNMP Exporter**: Metrics extraction based on dynamic module configurations.
3. **FastAPI Backend**: API server, automated collection orchestrator, and data unpivoting layer.
4. **Manager**: SNMP polling coordinator — stores metrics in DuckDB, manages agent registration and device config distribution.
5. **React Frontend**: Premium dashboard for visualization and system administration.
6. **SNMP Simulator**: Built-in simulator for robust testing and validation.

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
   # Edit .env — at minimum set MANAGER_API_KEY to a strong secret value
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
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Manager API: http://localhost:8001
   - SNMP Exporter: http://localhost:9116

## Simulation & Testing

The project includes an automated end-to-end simulation workflow to verify the system without needing real hardware.

To run the simulation:
```bash
make simulation
```

**What this does:**
1. Starts all services, including a dedicated `snmp-simulator` container.
2. Runs database migrations.
3. Automatically adds a test device ("Test-Simulator") via the API.
4. Triggers an immediate SNMP collection.
5. Verifies that metrics (Interface Status, In/Out Octets, Packets) are physically stored in the database.
6. Reports the number of interfaces found and metrics collected.

**Cleanup:**
To remove the test device and simulation data:
```bash
make clean-simulation
```

## Usage Guide

### Configuring Modules and Schedules

1. Navigate to **Configuration** page
2. **Device Schedules Table**: View and manage polling intervals for all devices at once. You can pause collection or adjust frequencies directly.
3. **Module Definitions**: Edit the YAML configuration for your SNMP modules directly in the browser. Changes are applied automatically to the exporter.

### Viewing Metrics

1. Navigate to **Metrics** page
2. Select a **Device**, then a **Module** (e.g., if_mib), and finally the specific **Metrics** you wish to graph.
3. Choose an interface (if applicable) and time range.
4. View interactive, synchronized charts for traffic, status, and error statistics.

## Configuration

### Environment Variables

Edit `.env` to customize:

```bash
# Database
POSTGRES_DB=snmp_metrics
POSTGRES_USER=snmpuser
POSTGRES_PASSWORD=snmppass
POSTGRES_PORT=5432

# SNMP Exporter
SNMP_EXPORTER_PORT=9116

# Backend
BACKEND_PORT=8000

# Frontend
FRONTEND_PORT=3000

# Collection
DEFAULT_COLLECTION_INTERVAL=60

# Manager
MANAGER_API_KEY=change-me-in-production
```

## Makefile Commands

```bash
make help              # Show all available commands
make build             # Build all Docker containers
make up                # Start the application
make down              # Stop the application
make logs              # View logs from all containers
make logs-backend      # View backend logs
make logs-frontend     # View frontend logs
make logs-manager      # View manager logs
make clean             # Remove containers and volumes
make reset             # Full reset (clean + rebuild + start)
make migrate           # Run database migrations
make simulation        # Run end-to-end simulation test
make clean-simulation  # Remove simulation data
make shell-backend     # Open shell in backend container
make shell-db          # Open PostgreSQL shell
make test              # Run manager tests
make status            # Show container status
make restart-backend   # Restart backend container
make restart-frontend  # Restart frontend container
make restart-exporter  # Restart SNMP exporter container
make dev-frontend      # Run frontend locally (npm start)
make dev-backend       # Run backend locally (uvicorn --reload)
```

## Database Schema

The PostgreSQL database uses TimescaleDB and a modular schema:

- **devices**: Network device information with linked SNMP modules.
- **if_mib_metrics**: Optimized wide table for interface statistics (high performance).
- **snmp_metrics**: Generic time-series storage for other modules (fallback).
- **collection_schedules**: Per-device collection timing and status.

The manager service maintains a separate DuckDB database (`data/db/metrics.db`) for SNMP poll results.

## Troubleshooting

### Database connection failed: "FATAL: role 'snmpuser' does not exist"

**Cause:** You likely have a local PostgreSQL instance running on your machine on port 5432, conflicting with the Docker container.
**Solution:**
1. Stop local Postgres: `brew services stop postgresql` or `pkill -f postgres`
2. OR Change the Docker port in `.env`: `POSTGRES_PORT=5433` then run `make down && make up`.

### Application won't start

```bash
make logs  # Check logs for errors
make clean # Clean up
make build # Rebuild
make up    # Start again
```

### SNMP collection not working

1. Verify device IP is reachable
2. Check SNMP community string is correct
3. Ensure ports are not blocked by firewall
4. View backend logs: `make logs-backend`
5. View manager logs: `make logs-manager`

## Project Structure

```
snmp-collector/
├── backend/                 # FastAPI application (device registry, metrics API)
│   ├── alembic/            # Database migrations
│   ├── routers/            # API endpoints
│   ├── services/           # Business logic
│   └── main.py             # Application entry
├── manager/                 # SNMP polling coordinator (DuckDB, agent registry)
│   ├── routers/            # API endpoints
│   ├── services/           # Ingest and registry logic
│   └── main.py             # Application entry
├── frontend/               # React application
│   ├── src/               # Source code
│   └── package.json       # Dependencies
├── prometheus/            # SNMP Exporter config (snmp.yml)
├── snmp-simulator/        # Simulation container (net-snmp)
├── scripts/               # Test scripts
├── data/                  # Runtime data (DuckDB, dead-letter queue, registry)
├── docker-compose.yml    # Container orchestration
├── Makefile             # Build automation
└── README.md            # This file
```

## License

See LICENSE file for details.

---

Built with Docker, FastAPI, React, PostgreSQL, and DuckDB
