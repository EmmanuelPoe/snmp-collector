# SNMP Metrics Collector

A comprehensive SNMP metrics collection system using Docker containers with Prometheus SNMP Exporter for data collection, PostgreSQL with TimescaleDB for time-series storage, FastAPI for orchestration and API services, and React for the frontend interface.

## 📋 Features

- **Device Management**: Add, edit, and manage network devices (routers/switches)
- **SNMP Metrics Collection**: Automated collection using Prometheus SNMP Exporter
- **Time-Series Storage**: PostgreSQL with TimescaleDB for efficient metric storage
- **OID Configuration**: Flexible SNMP OID management
- **Collection Scheduling**: Configurable collection intervals per device
- **Real-Time Visualization**: Interactive charts showing interface status and metrics
- **Modern UI**: Dark-mode interface with "Zinc/Cyan" theme and glassmorphism design
- **End-to-End Simulation**: Built-in test workflow with a simulated SNMP agent

## 🏗️ Architecture

The system consists of 5 Docker containers:

1. **PostgreSQL + TimescaleDB**: Time-series optimized database
2. **Prometheus SNMP Exporter**: Raw SNMP data collection
3. **FastAPI Backend**: API server, orchestration, and data processing
4. **React Frontend**: Modern web interface for management and visualization
5. **SNMP Simulator**: `net-snmp` agent for automated testing and verification

## 🚀 Quick Start

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
   # Edit .env if you want to change default values or ports
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

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - SNMP Exporter: http://localhost:9116

## 🧪 Simulation & Testing

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

## 📚 Usage Guide

### Managing Devices

1. Navigate to **Devices** page
2. Click **"+ Add Device"**
3. Fill in device information:
   - Name (e.g., "Router-01")
   - IP Address
   - SNMP Version (1, 2c, or 3)
   - SNMP Community string
   - Device Type (Router, Switch, etc.)
4. Click **Create**

### Viewing Metrics

1. Navigate to **Metrics** page
2. Select a device from the dropdown
3. Select an interface
4. Choose time range (1 hour to 1 week)
5. View interactive charts showing:
   - Interface status (Up/Down)
   - Packet statistics (In/Out)
   - Bandwidth usage (Octets In/Out)

## ⚙️ Configuration

### Environment Variables

Edit `.env` file to customize:

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
```

## 🛠️ Makefile Commands

```bash
make help            # Show all available commands
make build           # Build all Docker containers
make up              # Start the application
make down            # Stop the application
make logs            # View logs from all containers
make clean           # Remove containers and volumes
make reset           # Full reset (clean + rebuild + start)
make migrate         # Run database migrations
make simulation      # Run end-to-end simulation test
make clean-simulation # Remove simulation data
make shell-db        # Open PostgreSQL shell
```

## �️ Database Schema

The PostgreSQL database uses TimescaleDB for efficient time-series storage:

- **devices**: Network device information
- **snmp_metrics**: Time-series metrics (hypertable). Primary key is composite `(id, timestamp)`.
- **collection_configs**: SNMP OID configurations
- **collection_schedules**: Collection timing per device

## 🐛 Troubleshooting

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

## 📁 Project Structure

```
snmp-collector/
├── backend/                 # FastAPI application
│   ├── alembic/            # Database migrations
│   ├── routers/            # API endpoints
│   ├── services/           # Business logic
│   └── main.py             # Application entry
├── frontend/               # React application
│   ├── src/               # Source code
│   └── package.json       # Dependencies
├── prometheus/            # SNMP Exporter config (snmp.yml)
├── snmp-simulator/        # Simulation container (net-snmp)
├── scripts/               # Test scripts
├── docker-compose.yml    # Container orchestration
├── Makefile             # Build automation
└── README.md            # This file
```

## 📄 License

See LICENSE file for details.

---

Built with ❤️ using Docker, FastAPI, React, PostgreSQL, and Prometheus
