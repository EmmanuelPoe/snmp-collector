# SNMP Metrics Collector

A comprehensive SNMP metrics collection system using Docker containers with Prometheus SNMP Exporter for data collection, PostgreSQL with TimescaleDB for time-series storage, FastAPI for orchestration and API services, and React for the frontend interface.

## 📋 Features

- **Device Management**: Add, edit, and manage network devices (routers/switches)
- **SNMP Metrics Collection**: Automated collection using Prometheus SNMP Exporter
- **Time-Series Storage**: PostgreSQL with TimescaleDB for efficient metric storage
- **OID Configuration**: Flexible SNMP OID management
- **Collection Scheduling**: Configurable collection intervals per device
- **Real-Time Visualization**: Interactive charts showing interface status and metrics
- **Modern UI**: Premium dark-mode interface with glassmorphism design

## 🏗️ Architecture

The system consists of 4 Docker containers:

1. **PostgreSQL + TimescaleDB**: Time-series optimized database
2. **Prometheus SNMP Exporter**: Raw SNMP data collection
3. **FastAPI Backend**: API server, orchestration, and data processing
4. **React Frontend**: Modern web interface for management and visualization

## 🚀 Quick Start

### Prerequisites

- Docker (version 20.x or higher)
- Docker Compose (version 2.x or higher)
- Make (optional, for convenient commands)

### Installation

1. **Clone the repository**
   ```bash
   cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
   ```

2. **Set up environment variables** (optional)
   ```bash
   cp .env.example .env
   # Edit .env if you want to change default values
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

### First-Time Setup

After starting the application:

1. Navigate to http://localhost:3000
2. Go to "Devices" and add your first network device
3. Configure SNMP settings (IP, community string, etc.)
4. The system will automatically start collecting metrics
5. View metrics in the "Metrics" tab

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

### Configuring Collection

1. Navigate to **Configuration** page
2. Manage SNMP OIDs to collect
3. Adjust collection schedules per device
4. Reload configuration when changes are made

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

### Default SNMP OIDs

The system comes pre-configured with common interface metrics:

- `ifOperStatus` (1.3.6.1.2.1.2.2.1.8) - Interface status
- `ifInOctets` (1.3.6.1.2.1.2.2.1.10) - Inbound octets
- `ifOutOctets` (1.3.6.1.2.1.2.2.1.16) - Outbound octets
- `ifInUcastPkts` (1.3.6.1.2.1.2.2.1.11) - Inbound packets
- `ifOutUcastPkts` (1.3.6.1.2.1.2.2.1.17) - Outbound packets

## 🛠️ Makefile Commands

```bash
make help            # Show all available commands
make build           # Build all Docker containers
make up              # Start the application
make down            # Stop the application
make logs            # View logs from all containers
make logs-backend    # View backend logs
make logs-frontend   # View frontend logs
make clean           # Remove containers and volumes
make reset           # Full reset (clean + rebuild + start)
make migrate         # Run database migrations
make shell-backend   # Open shell in backend container
make shell-db        # Open PostgreSQL shell
make status          # Check container status
```

## 🔌 API Documentation

The FastAPI backend provides a comprehensive REST API:

### Devices
- `GET /devices` - List all devices
- `POST /devices` - Create new device
- `GET /devices/{id}` - Get device details
- `PUT /devices/{id}` - Update device
- `DELETE /devices/{id}` - Delete device

### Metrics
- `GET /metrics` - Query metrics with filters
- `GET /metrics/latest/{device_id}` - Get latest metrics
- `GET /metrics/interfaces/{device_id}` - List device interfaces
- `GET /metrics/stats/{device_id}/{interface_name}` - Get interface stats
- `POST /metrics/collect/{device_id}` - Trigger manual collection

### Configuration
- `GET /config/oids` - List SNMP OID configurations
- `POST /config/oids` - Add new OID
- `DELETE /config/oids/{id}` - Remove OID
- `GET /config/schedule/{device_id}` - Get collection schedule
- `PUT /config/schedule/{device_id}` - Update schedule
- `POST /config/reload` - Reload SNMP Exporter config

Full interactive documentation: http://localhost:8000/docs

## 🗄️ Database Schema

The PostgreSQL database uses TimescaleDB for efficient time-series storage:

- **devices**: Network device information
- **snmp_metrics**: Time-series metrics (hypertable)
- **collection_configs**: SNMP OID configurations
- **collection_schedules**: Collection timing per device

## 🐛 Troubleshooting

### Application won't start

```bash
make logs  # Check logs for errors
make clean # Clean up
make build # Rebuild
make up    # Start again
```

### Database connection errors

```bash
make shell-db  # Check if database is accessible
# Inside PostgreSQL shell:
\dt  # List tables
```

### SNMP collection not working

1. Verify device IP is reachable
2. Check SNMP community string is correct
3. Ensure SNMP version matches device config
4. Check device has SNMP enabled
5. View backend logs: `make logs-backend`

### Frontend can't connect to backend

1. Verify backend is running: `make status`
2. Check backend logs: `make logs-backend`
3. Ensure ports are not blocked by firewall

## 📁 Project Structure

```
snmp-collector/
├── backend/                 # FastAPI application
│   ├── alembic/            # Database migrations
│   ├── routers/            # API endpoints
│   ├── services/           # Business logic
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   └── main.py             # Application entry
├── frontend/               # React application
│   ├── public/            # Static files
│   ├── src/               # Source code
│   │   ├── components/    # React components
│   │   └── services/      # API client
│   └── package.json       # Dependencies
├── prometheus/            # SNMP Exporter config
│   ├── snmp.yml          # OID definitions
│   └── Dockerfile        # Custom image
├── docker-compose.yml    # Container orchestration
├── Makefile             # Build automation
└── README.md            # This file
```

## 🔮 Future Enhancements

- Authentication and user management
- Alert notifications for device status changes
- Historical data retention policies
- Custom dashboard creation
- Export metrics to external monitoring systems
- Multi-tenant support

## 📄 License

See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

---

Built with ❤️ using Docker, FastAPI, React, PostgreSQL, and Prometheus
