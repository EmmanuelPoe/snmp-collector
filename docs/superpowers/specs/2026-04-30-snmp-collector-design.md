# Enterprise SNMP Collector System — Design Spec

**Date:** 2026-04-30  
**Status:** Approved  
**Project:** snmp-collector-v2 (standalone, new project)

---

## 1. Overview

A distributed SNMP collection system consisting of lightweight Go collector agents and a centralized FastAPI manager. Agents install on any system, self-register with the manager, collect SNMP v3 data and traps from network devices, buffer data locally as Parquet files, and offload to the manager every 5 minutes. The manager stores all ingested data in DuckDB and exposes a professional dark-mode web UI for agent management, device inventory, and data querying.

### Key Design Goals

- **Easy deployment:** Agent is a single Go binary. Manager is a single Docker container.
- **Resilient:** Agents buffer up to 24 hours of data locally if the manager goes offline.
- **Enterprise-grade:** SNMP v3 authPriv, API key auth, checksum verification, deduplication, dead-letter store, graceful shutdown.
- **Efficient storage:** Columnar Parquet on agents, DuckDB on manager (Parquet-native bulk ingest).
- **Observable:** Agent health endpoint, manager heartbeat tracking, web UI status dashboard.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    COLLECTOR AGENT (Go binary)               │
│                                                              │
│  ┌──────────────────┐   ┌──────────────────┐                │
│  │   SNMP Poller    │   │  Trap Listener   │                │
│  │  60s, v3 authPriv│   │  UDP :162        │                │
│  │  1000 devices    │   │  event-driven    │                │
│  │  staggered polls │   │                  │                │
│  └────────┬─────────┘   └────────┬─────────┘                │
│           │                      │                           │
│           ▼                      ▼                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              In-Memory Write Buffer                   │   │
│  │         (flushed to Parquet on 5-min window)          │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          │                                   │
│              ┌───────────▼──────────┐                       │
│              │    Parquet Store     │  wall-clock aligned    │
│              │  /data/polls/        │  5-min windows         │
│              │  /data/traps/        │  24h max retention     │
│              └───────────┬──────────┘                       │
│                          │                                   │
│              ┌───────────▼──────────┐                       │
│              │   Offload Worker     │  every 5min if online  │
│              │   HTTP POST + SHA256 │  queues if offline     │
│              └───────────┬──────────┘                       │
│                          │                                   │
│              ┌───────────▼──────────┐                       │
│              │  Health Endpoint     │  GET :8080/health      │
│              │  Heartbeat sender    │  POST /heartbeat 30s   │
│              └──────────────────────┘                       │
└──────────────────────────┼──────────────────────────────────┘
                           │  HTTPS + API Key
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   MANAGER (Docker, FastAPI)                  │
│                                                              │
│  REST API                                                    │
│  ├── POST /register        ← agent startup                  │
│  ├── POST /heartbeat       ← every 30s per agent            │
│  ├── POST /ingest          ← Parquet file upload            │
│  ├── GET  /config/{id}     ← device list pull               │
│  └── CRUD /devices         ← device inventory management    │
│                                                              │
│  Web UI (Jinja2 + HTMX + Tailwind, dark NOC theme)          │
│  ├── /              Dashboard (counts, alerts, status)       │
│  ├── /ui/agents     Agent list, health, deregister           │
│  ├── /ui/devices    Device inventory, add/remove             │
│  └── /ui/query      Poll + trap explorer, raw SQL            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Agent Registry                                      │    │
│  │  in-memory dict + persisted registry.json           │    │
│  │  { agent_id, hostname, ip, last_seen, status, key } │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  DuckDB (mounted volume /data/db/metrics.db)         │    │
│  │  ├── snmp_polls   (agent_id, device_ip, oid,        │    │
│  │  │                 value, collected_at)              │    │
│  │  ├── snmp_traps   (agent_id, device_ip, trap_oid,   │    │
│  │  │                 varbinds JSON, received_at)       │    │
│  │  └── ingest_log   (file_id PK, ingested_at,         │    │
│  │                    row_count)                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  /data/dead-letter/    ← failed ingests with error metadata │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Collector Agent

### Technology
- **Language:** Go
- **Key libraries:** `gosnmp` (SNMP v3), `parquet-go` (Parquet write), `net/http` (offload + health), `gopkg.in/yaml.v3` (config)
- **Deployment:** Single static binary. Install via curl or package manager.

### Configuration (`agent.yaml`)
```yaml
manager_url: https://manager.example.com:8000
api_key: <secret>
data_dir: /var/lib/snmp-agent/data
agent_id: ""                  # empty on first run; persisted after registration
health_port: 8080
```

SNMP v3 credentials (username, auth password, priv password, auth protocol, priv protocol) are **per-device** and stored in the manager's `devices` table. They are returned to the agent as part of the device list on registration and config pull — never stored in `agent.yaml`.

### Startup Sequence
1. Load `agent.yaml`
2. If `agent_id` is empty: `POST /register` → receive `agent_id` + device list + store both to config
3. If `agent_id` set: `GET /config/{agent_id}` → refresh device list
4. Start poll worker pool, trap listener, offload worker, heartbeat sender, health endpoint

### Poll Worker Pool
- One goroutine per device, started with staggered delay: `delay = hash(device_ip) % 60` seconds
- Each goroutine loops: poll → write to in-memory buffer → sleep 60s
- In-memory buffer flushed to Parquet on wall-clock 5-minute boundaries (:00, :05, :10...)
- SNMP v3 authPriv credentials per device (received from manager config)

### Trap Listener
- UDP listener on `:162`
- Parsed traps written to separate in-memory trap buffer
- Flushed to `/data/traps/` Parquet on same 5-min boundary as polls

### Parquet File Naming
```
/data/polls/2026-04-30T14:05:00Z.parquet
/data/traps/2026-04-30T14:05:00Z.parquet
```

### Offload Worker
- Runs every 5 minutes (aligned to window close)
- Scans `/data/polls/` and `/data/traps/` for closed Parquet files (not the currently-open window)
- For each file:
  1. Compute SHA-256
  2. `POST /ingest` with `X-File-ID: {agent_id}_{window_start}_{type}` and `X-SHA256: {hash}`
  3. On 200: delete local file
  4. On failure: retain file, retry next cycle
- Files older than 24h from their `collected_at` window start are pruned regardless of upload status

### Graceful Shutdown (SIGTERM)
1. Stop accepting new polls
2. Flush in-memory buffer to Parquet (mark as pending)
3. Attempt one final offload of all pending files
4. Exit

### Health Endpoint (`GET :8080/health`)
```json
{
  "status": "ok",
  "agent_id": "nyc-agent-01",
  "manager_connected": true,
  "pending_uploads": 2,
  "poll_success_rate_1m": 0.997,
  "trap_count_1h": 14,
  "uptime_seconds": 3612
}
```

---

## 4. Manager

### Technology
- **Language:** Python 3.12
- **Framework:** FastAPI
- **Database:** DuckDB (embedded, file-based)
- **Templates:** Jinja2
- **UI:** HTMX + Tailwind CSS (CDN)
- **Deployment:** Single Docker container

### Docker
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml (production)
services:
  manager:
    build: ./manager
    ports:
      - "8000:8000"
    volumes:
      - ./data/db:/data/db
      - ./data/dead-letter:/data/dead-letter
      - ./data/registry:/data/registry
    environment:
      - MANAGER_API_KEY=<secret>
      - DB_PATH=/data/db/metrics.db
      - REGISTRY_PATH=/data/registry/registry.json
```

### Agent Registry
- In-memory Python dict keyed by `agent_id`
- Persisted to `registry.json` on every write (register, heartbeat, deregister)
- Loaded from `registry.json` on startup
- Agent status logic:
  - `online`: last heartbeat < 90s ago
  - `degraded`: last heartbeat 90s–5min ago
  - `offline`: last heartbeat > 5min ago

### REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Agent registers, receives device list |
| POST | `/heartbeat` | Update agent last_seen |
| POST | `/ingest` | Parquet file upload + ingest |
| GET | `/config/{agent_id}` | Pull current device list |
| GET | `/devices` | List all devices |
| POST | `/devices` | Add device |
| DELETE | `/devices/{id}` | Remove device |

### Ingest Pipeline
1. Receive multipart file upload
2. Verify `X-SHA256` header against computed hash
3. Check `ingest_log` for duplicate `file_id` — skip if exists
4. `INSERT INTO snmp_polls SELECT * FROM read_parquet(tmp_file)` (or `snmp_traps`)
5. Write to `ingest_log`
6. Delete temp file
7. On any failure: move file to `/data/dead-letter/{file_id}.parquet` with `{file_id}.error.json`

### DuckDB Schema
```sql
CREATE TABLE snmp_polls (
    agent_id     VARCHAR NOT NULL,
    device_ip    VARCHAR NOT NULL,
    oid          VARCHAR NOT NULL,
    value        VARCHAR,
    collected_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE snmp_traps (
    agent_id     VARCHAR NOT NULL,
    device_ip    VARCHAR NOT NULL,
    trap_oid     VARCHAR NOT NULL,
    varbinds     JSON,
    received_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE ingest_log (
    file_id      VARCHAR PRIMARY KEY,
    ingested_at  TIMESTAMPTZ NOT NULL,
    row_count    INTEGER NOT NULL
);

-- Device inventory (source of truth for all agent device lists)
CREATE TABLE devices (
    id           VARCHAR PRIMARY KEY,   -- UUID
    ip           VARCHAR NOT NULL,
    hostname     VARCHAR,
    snmp_version VARCHAR DEFAULT 'v3',
    username     VARCHAR NOT NULL,
    auth_protocol VARCHAR NOT NULL,     -- SHA / SHA256 / SHA384 / SHA512
    auth_password VARCHAR NOT NULL,
    priv_protocol VARCHAR NOT NULL,     -- AES / AES256
    priv_password VARCHAR NOT NULL,
    assigned_agent_id VARCHAR,          -- NULL = unassigned
    created_at   TIMESTAMPTZ NOT NULL,
    last_polled_at TIMESTAMPTZ
);
```

> **Note:** Dead-letter files in `/data/dead-letter/` require manual operator review and replay. They do not self-clear. Monitor dead-letter count via the dashboard alert.

---

## 5. Web UI

### Technology
- Jinja2 templates served by FastAPI
- HTMX for dynamic partial updates (no page reloads)
- Tailwind CSS via CDN (no build step)
- Dark NOC theme: `gray-900` backgrounds, green/amber/red status badges, monospace for IPs/OIDs

### Pages

#### Dashboard (`/`)
- Online / degraded / offline agent counts with color badges
- Total polls ingested (last 24h)
- Total traps received (last 24h)
- Dead-letter queue depth (amber warning if > 0)
- Agent status table summary
- Auto-refreshes every 30s via `hx-trigger="every 30s" hx-get="/ui/partials/dashboard"`

#### Agents (`/ui/agents`)
- Full table: agent ID, hostname, IP, status badge, last seen, device count, pending uploads
- Click row → detail panel: heartbeat history, upload log, health endpoint link
- Actions: deregister (confirm dialog), force config push
- Status badges auto-refresh every 30s

#### Devices (`/ui/devices`)
- Table: IP, hostname, SNMP credentials (masked), assigned agent, last polled timestamp
- Inline "Add Device" form via HTMX (slides in, no page reload)
- Remove button per row (confirm inline)
- Filter by assigned agent

#### Query (`/ui/query`)
- **Polls tab:** filter by agent, device IP, OID prefix, time range → paginated results table
- **Traps tab:** filter by agent, device IP, trap OID, time range → paginated results table
- **SQL tab:** read-only textarea, SELECT-only enforcement, results as HTML table

---

## 6. Enterprise Reliability Features

| Feature | Implementation |
|---------|---------------|
| Poll stagger | `delay = hash(device_ip) % 60` — spreads 1000 devices across 60s |
| Wall-clock window alignment | 5-min boundaries at :00, :05, :10... regardless of agent start time |
| Idempotent ingest | `file_id = {agent_id}_{window_start}_{type}` checked in `ingest_log` |
| Checksum verification | SHA-256 in `X-SHA256` header, verified before ingest |
| Dead-letter store | Failed ingests → `/data/dead-letter/` with error metadata |
| 24h local buffer | Agent retains Parquet files up to 24h, auto-prunes older |
| Graceful shutdown | SIGTERM flushes buffer, attempts final upload, then exits |
| Config push | Manager returns device list on registration and `/config/{id}` pull |
| Agent registry persistence | `registry.json` survives manager container restarts |
| DuckDB on mounted volume | Data survives container upgrades and crashes |
| Health endpoint | `GET :8080/health` — monitorable by external systems |

---

## 7. Local Development & Test Environment

### Stack (4 containers)
```yaml
# docker-compose.dev.yml
services:
  snmpsim:       # simulates 10 SNMP v3 devices on :161
  trap-gen:      # Alpine + net-snmp, fires snmptrap every 30s
  agent:         # Go binary, ENV MANAGER_URL=http://manager:8000
  manager:       # FastAPI + DuckDB
```

### snmpsim
- Python `snmpsim` image
- Simulates 10 virtual devices using bundled `.snmprec` data files (ifMIB, hostResources)
- v3 authPriv credentials matching agent config
- Exposes UDP `:161`

### trap-gen
- Alpine + net-snmp tools
- Shell loop: `while true; do snmptrap ...; sleep 30; done`
- Sends linkDown/linkUp traps to agent `:162`

### Agent (dev container)
- Multi-stage Dockerfile: `golang:1.22-alpine` build → `alpine:3.19` runtime
- `ENV MANAGER_URL=http://manager:8000`
- Mounts `./dev-data/agent:/data` — inspect Parquet files locally
- Registers with manager on startup, polls snmpsim devices

### Manager (dev container)
- Same image as production
- Mounts `./dev-data/manager:/data`
- Query DuckDB directly: `duckdb ./dev-data/manager/db/metrics.db`

### Makefile
```makefile
make up              # start all 4 containers
make down            # stop everything
make logs            # tail all containers
make query           # open DuckDB CLI against manager DB
make reset           # wipe dev-data + restart
make status          # curl manager /agents — show registered agents
make sim-trap        # fire one manual trap for testing
```

### Validation Flow
1. `make up`
2. Manager starts on `:8000`, snmpsim on `:161`
3. Agent registers → receives 10 simulated device IPs
4. Agent begins staggered polling every 60s
5. `trap-gen` fires traps every 30s → agent buffers
6. After 5 minutes → agent flushes first Parquet → manager ingests → DuckDB has rows
7. `make query` → `SELECT COUNT(*) FROM snmp_polls;` confirms data flow
8. Open `http://localhost:8000` → dashboard shows agent online, poll counts

---

## 8. Project Structure

```
snmp-collector-v2/
├── agent/                        # Go collector agent
│   ├── cmd/agent/main.go         # entrypoint
│   ├── internal/
│   │   ├── config/               # config loading + persistence
│   │   ├── poller/               # SNMP v3 poll worker pool
│   │   ├── trap/                 # UDP trap listener
│   │   ├── buffer/               # in-memory write buffer
│   │   ├── parquet/              # Parquet writer
│   │   ├── offload/              # upload worker + retry logic
│   │   ├── heartbeat/            # heartbeat sender
│   │   └── health/               # health HTTP endpoint
│   ├── Dockerfile
│   └── agent.yaml.example
│
├── manager/                      # FastAPI manager
│   ├── main.py                   # FastAPI app + lifespan
│   ├── routers/
│   │   ├── registration.py       # /register, /heartbeat, /config
│   │   ├── ingest.py             # /ingest
│   │   ├── devices.py            # /devices CRUD
│   │   └── ui.py                 # web UI routes
│   ├── services/
│   │   ├── registry.py           # agent registry (memory + JSON)
│   │   ├── database.py           # DuckDB connection + queries
│   │   └── ingest.py             # Parquet ingest pipeline
│   ├── templates/
│   │   ├── base.html             # Tailwind dark layout
│   │   ├── dashboard.html
│   │   ├── agents.html
│   │   ├── devices.html
│   │   └── query.html
│   ├── static/                   # any local static assets
│   ├── Dockerfile
│   └── requirements.txt
│
├── dev/
│   ├── docker-compose.dev.yml    # full dev stack
│   ├── snmpsim/
│   │   └── snmpv3.conf           # v3 user config for simulator
│   ├── trap-gen/
│   │   ├── Dockerfile
│   │   └── send-traps.sh
│   └── dev-data/                 # gitignored, runtime data
│       ├── agent/
│       └── manager/
│
├── docker-compose.yml            # production manager-only compose
├── Makefile
└── README.md
```

---

## 9. Security

- **Transport:** HTTPS (TLS termination at reverse proxy or API Gateway in production; HTTP acceptable in dev)
- **Auth:** API key per agent, passed in `Authorization: Bearer <key>` header
- **SNMP credentials:** Stored in manager DB, never logged. Passed to agents in registration response over HTTPS only.
- **SQL tab:** Enforces SELECT-only. Statements parsed before execution; any non-SELECT rejected with 400.
- **Parquet ingest:** Temp files written to `/tmp`, deleted immediately after ingest. Never persisted in app directory.

---

## 10. README

The full README.md (for project root) covers:
- System overview and architecture diagram
- Prerequisites (Docker, Go 1.22+, make)
- Quick start (dev): `git clone` → `make up` → open `http://localhost:8000`
- Quick start (production): docker-compose manager only + agent binary install
- Agent install guide (binary download + `agent.yaml` config)
- Manager configuration (environment variables)
- Makefile reference
- Web UI usage guide
- Troubleshooting section
- Architecture decision notes

README.md is generated as part of the implementation plan.
