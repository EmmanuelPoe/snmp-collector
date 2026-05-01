# Manager Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI manager container with DuckDB storage, agent registration API, device inventory API, and Parquet ingest pipeline — deployable as a single Docker container.

**Architecture:** Single FastAPI app (uvicorn), embedded DuckDB for all persistent storage, in-memory agent registry backed by JSON file. Async write lock serializes all DuckDB writes. All routes require API key auth via Bearer token.

**Tech Stack:** Python 3.12, FastAPI 0.115, DuckDB 1.1, pyarrow 17, pydantic-settings 2.5, python-multipart, pytest, httpx

---

## File Map

```
manager/
├── main.py                  # app factory, lifespan, router mounting
├── config.py                # env var settings via pydantic-settings
├── db.py                    # DuckDB connection, schema, query/execute/ingest helpers
├── registry.py              # AgentRegistry: in-memory dict + JSON persistence
├── models.py                # Pydantic request/response models
├── auth.py                  # Bearer API key FastAPI dependency
├── routers/
│   ├── __init__.py
│   ├── registration.py      # POST /register, POST /heartbeat, GET /config/{id}, GET /agents
│   ├── devices.py           # GET/POST /devices, DELETE /devices/{id}
│   └── ingest.py            # POST /ingest
├── services/
│   ├── __init__.py
│   └── ingest.py            # SHA256 verify, dedup check, parquet bulk load, dead-letter
├── tests/
│   ├── conftest.py          # fixtures: patched settings, TestClient, sample Parquet
│   ├── test_db.py
│   ├── test_registry.py
│   ├── test_ingest_service.py
│   ├── test_registration_api.py
│   ├── test_devices_api.py
│   └── test_ingest_api.py
├── Dockerfile
├── requirements.txt
└── .env.example
```

All imports are absolute (e.g. `from config import settings`). Run `uvicorn main:app` and `pytest` from the `manager/` directory.

---

## Task 1: Project Scaffold

**Files:**
- Create: `manager/requirements.txt`
- Create: `manager/.env.example`
- Create: `manager/config.py`
- Create: `manager/main.py` (skeleton only)
- Create: `manager/routers/__init__.py`
- Create: `manager/services/__init__.py`
- Create: `manager/tests/conftest.py`

- [ ] **Step 1: Create directory structure**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
mkdir -p manager/routers manager/services manager/tests
touch manager/routers/__init__.py manager/services/__init__.py
```

- [ ] **Step 2: Create `manager/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
duckdb==1.1.0
pyarrow==17.0.0
pydantic-settings==2.5.2
python-multipart==0.0.12
jinja2==3.1.4
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

- [ ] **Step 3: Create `manager/.env.example`**

```
MANAGER_API_KEY=change-me
DB_PATH=/data/db/metrics.db
REGISTRY_PATH=/data/registry/registry.json
DEAD_LETTER_PATH=/data/dead-letter
```

- [ ] **Step 4: Create `manager/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    manager_api_key: str
    db_path: str = "/data/db/metrics.db"
    registry_path: str = "/data/registry/registry.json"
    dead_letter_path: str = "/data/dead-letter"

    model_config = {"env_file": ".env"}

settings = Settings()
```

- [ ] **Step 5: Create `manager/main.py` skeleton**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create `manager/tests/conftest.py`**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone

@pytest.fixture(autouse=True)
def patch_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_API_KEY", "test-key")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setenv("DEAD_LETTER_PATH", str(tmp_path / "dead-letter"))
    # Force settings reload
    import config
    config.settings = config.Settings()

@pytest.fixture
def reset_db():
    import db
    db._conn = None
    yield
    if db._conn:
        db._conn.close()
        db._conn = None

@pytest.fixture
def reset_registry():
    import registry as reg_mod
    reg_mod.registry._agents.clear()

@pytest.fixture
def client(patch_settings, reset_db, reset_registry):
    from main import app
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-key"}

@pytest.fixture
def sample_polls_parquet(tmp_path):
    rows = 5
    table = pa.table({
        "agent_id": pa.array(["agent-01"] * rows),
        "device_ip": pa.array(["192.168.1.1"] * rows),
        "oid": pa.array(["1.3.6.1.2.1.1.3.0"] * rows),
        "value": pa.array(["12345"] * rows),
        "collected_at": pa.array([datetime.now(timezone.utc)] * rows, type=pa.timestamp("us", tz="UTC")),
    })
    path = tmp_path / "polls.parquet"
    pq.write_table(table, path)
    return path

@pytest.fixture
def sample_traps_parquet(tmp_path):
    rows = 3
    table = pa.table({
        "agent_id": pa.array(["agent-01"] * rows),
        "device_ip": pa.array(["192.168.1.1"] * rows),
        "trap_oid": pa.array(["1.3.6.1.6.3.1.1.5.3"] * rows),
        "varbinds": pa.array(['{"ifIndex": "1"}'] * rows),
        "received_at": pa.array([datetime.now(timezone.utc)] * rows, type=pa.timestamp("us", tz="UTC")),
    })
    path = tmp_path / "traps.parquet"
    pq.write_table(table, path)
    return path
```

- [ ] **Step 7: Install dependencies and verify scaffold**

```bash
cd manager
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
```

Expected: 0 tests collected, 0 errors.

- [ ] **Step 8: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/
git commit -m "feat: scaffold manager project structure and dependencies"
```

---

## Task 2: DuckDB Setup

**Files:**
- Create: `manager/db.py`
- Create: `manager/tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `manager/tests/test_db.py`:

```python
import pytest

def test_schema_creates_all_tables(reset_db):
    import db
    conn = db.get_db()
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    assert "snmp_polls" in tables
    assert "snmp_traps" in tables
    assert "ingest_log" in tables
    assert "devices" in tables

def test_query_returns_rows(reset_db):
    import db
    conn = db.get_db()
    conn.execute(
        "INSERT INTO devices VALUES ('id1','1.2.3.4',NULL,'v3','user','SHA256',"
        "'authpass','AES256','privpass',NULL,current_timestamptz,NULL)"
    )
    rows = db.query("SELECT id FROM devices WHERE id = ?", ["id1"])
    assert len(rows) == 1
    assert rows[0][0] == "id1"

@pytest.mark.asyncio
async def test_execute_write(reset_db):
    import db
    await db.execute(
        "INSERT INTO devices VALUES (?,?,NULL,'v3',?,?,?,?,?,NULL,current_timestamptz,NULL)",
        ["id2", "1.2.3.5", "user", "SHA256", "auth", "AES256", "priv"]
    )
    rows = db.query("SELECT id FROM devices WHERE id = ?", ["id2"])
    assert rows[0][0] == "id2"

@pytest.mark.asyncio
async def test_ingest_parquet_polls(reset_db, sample_polls_parquet):
    import db
    count = await db.ingest_parquet("snmp_polls", str(sample_polls_parquet))
    assert count == 5
    rows = db.query("SELECT COUNT(*) FROM snmp_polls")
    assert rows[0][0] == 5

@pytest.mark.asyncio
async def test_ingest_parquet_traps(reset_db, sample_traps_parquet):
    import db
    count = await db.ingest_parquet("snmp_traps", str(sample_traps_parquet))
    assert count == 3

def test_close_and_reopen(reset_db, tmp_path, monkeypatch):
    import db, config
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    config.settings = config.Settings()
    db._conn = None
    conn1 = db.get_db()
    conn1.execute("INSERT INTO devices VALUES ('id3','1.2.3.6',NULL,'v3','u','SHA256','a','AES256','p',NULL,current_timestamptz,NULL)")
    db.close_db()
    conn2 = db.get_db()
    rows = db.query("SELECT id FROM devices WHERE id = ?", ["id3"])
    assert rows[0][0] == "id3"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd manager
pytest tests/test_db.py -v
```

Expected: `ImportError: No module named 'db'`

- [ ] **Step 3: Create `manager/db.py`**

```python
import duckdb
import asyncio
from pathlib import Path
from config import settings

_conn: duckdb.DuckDBPyConnection | None = None
_write_lock = asyncio.Lock()

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS snmp_polls (
        agent_id     VARCHAR NOT NULL,
        device_ip    VARCHAR NOT NULL,
        oid          VARCHAR NOT NULL,
        value        VARCHAR,
        collected_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS snmp_traps (
        agent_id     VARCHAR NOT NULL,
        device_ip    VARCHAR NOT NULL,
        trap_oid     VARCHAR NOT NULL,
        varbinds     VARCHAR,
        received_at  TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ingest_log (
        file_id      VARCHAR PRIMARY KEY,
        ingested_at  TIMESTAMPTZ NOT NULL,
        row_count    INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS devices (
        id                VARCHAR PRIMARY KEY,
        ip                VARCHAR NOT NULL,
        hostname          VARCHAR,
        snmp_version      VARCHAR DEFAULT 'v3',
        username          VARCHAR NOT NULL,
        auth_protocol     VARCHAR NOT NULL,
        auth_password     VARCHAR NOT NULL,
        priv_protocol     VARCHAR NOT NULL,
        priv_password     VARCHAR NOT NULL,
        assigned_agent_id VARCHAR,
        created_at        TIMESTAMPTZ NOT NULL,
        last_polled_at    TIMESTAMPTZ
    )""",
]


def get_db() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        _conn = duckdb.connect(settings.db_path)
        for stmt in _SCHEMA:
            _conn.execute(stmt)
    return _conn


def close_db() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def query(sql: str, params: list | None = None) -> list[tuple]:
    conn = get_db()
    if params:
        return conn.execute(sql, params).fetchall()
    return conn.execute(sql).fetchall()


async def execute(sql: str, params: list | None = None) -> None:
    async with _write_lock:
        conn = get_db()
        if params:
            conn.execute(sql, params)
        else:
            conn.execute(sql)


async def ingest_parquet(table: str, file_path: str) -> int:
    """Bulk load parquet file into table. Returns number of rows inserted."""
    async with _write_lock:
        conn = get_db()
        before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.execute(f"INSERT INTO {table} SELECT * FROM read_parquet($1)", [file_path])
        after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return after - before
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd manager
pytest tests/test_db.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/db.py manager/tests/test_db.py
git commit -m "feat: add DuckDB setup with schema and query helpers"
```

---

## Task 3: Agent Registry

**Files:**
- Create: `manager/registry.py`
- Create: `manager/tests/test_registry.py`

- [ ] **Step 1: Write failing tests**

Create `manager/tests/test_registry.py`:

```python
import pytest
import time
from datetime import datetime, timezone, timedelta

def test_register_creates_agent(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    agent_id = reg.register("host-01", "10.0.0.1")
    assert agent_id.startswith("host-01-")
    assert reg.get(agent_id) is not None

def test_register_persists_to_json(tmp_path, monkeypatch, reset_registry):
    import config
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "registry.json"))
    config.settings = config.Settings()
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    reg.register("host-02", "10.0.0.2")
    assert (tmp_path / "registry.json").exists()

def test_reload_restores_agents(tmp_path, monkeypatch, reset_registry):
    import config
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path / "reg.json"))
    config.settings = config.Settings()
    from registry import AgentRegistry
    reg1 = AgentRegistry.__new__(AgentRegistry)
    reg1._agents = {}
    agent_id = reg1.register("host-03", "10.0.0.3")
    reg1._persist()
    reg2 = AgentRegistry.__new__(AgentRegistry)
    reg2._agents = {}
    reg2._load()
    assert reg2.get(agent_id) is not None
    assert reg2.get(agent_id).hostname == "host-03"

def test_heartbeat_updates_last_seen(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    agent_id = reg.register("host-04", "10.0.0.4")
    reg.heartbeat(agent_id, pending_uploads=3)
    assert reg.get(agent_id).last_seen is not None
    assert reg.get(agent_id).pending_uploads == 3

def test_heartbeat_unknown_agent_raises(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    with pytest.raises(KeyError):
        reg.heartbeat("nonexistent", pending_uploads=0)

def test_status_online(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    agent.last_seen = datetime.now(timezone.utc)
    assert agent.status == "online"

def test_status_degraded(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    agent.last_seen = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert agent.status == "degraded"

def test_status_offline(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    agent.last_seen = datetime.now(timezone.utc) - timedelta(seconds=360)
    assert agent.status == "offline"

def test_status_never_seen(reset_registry):
    from registry import AgentInfo
    agent = AgentInfo("id", "host", "ip")
    assert agent.status == "offline"

def test_deregister(reset_registry):
    from registry import AgentRegistry
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._agents = {}
    agent_id = reg.register("host-05", "10.0.0.5")
    reg.deregister(agent_id)
    assert reg.get(agent_id) is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd manager
pytest tests/test_registry.py -v
```

Expected: `ImportError: No module named 'registry'`

- [ ] **Step 3: Create `manager/registry.py`**

```python
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from config import settings


class AgentInfo:
    def __init__(self, agent_id: str, hostname: str, ip: str):
        self.agent_id = agent_id
        self.hostname = hostname
        self.ip = ip
        self.last_seen: datetime | None = None
        self.pending_uploads: int = 0
        self.registered_at = datetime.now(timezone.utc)

    @property
    def status(self) -> str:
        if self.last_seen is None:
            return "offline"
        age = (datetime.now(timezone.utc) - self.last_seen).total_seconds()
        if age < 90:
            return "online"
        if age < 300:
            return "degraded"
        return "offline"

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "hostname": self.hostname,
            "ip": self.ip,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "pending_uploads": self.pending_uploads,
            "registered_at": self.registered_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentInfo":
        agent = cls(d["agent_id"], d["hostname"], d["ip"])
        if d.get("last_seen"):
            agent.last_seen = datetime.fromisoformat(d["last_seen"])
        agent.pending_uploads = d.get("pending_uploads", 0)
        agent.registered_at = datetime.fromisoformat(
            d.get("registered_at", datetime.now(timezone.utc).isoformat())
        )
        return agent


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentInfo] = {}
        self._load()

    def register(self, hostname: str, ip: str) -> str:
        agent_id = f"{hostname}-{uuid.uuid4().hex[:8]}"
        info = AgentInfo(agent_id, hostname, ip)
        info.last_seen = datetime.now(timezone.utc)
        self._agents[agent_id] = info
        self._persist()
        return agent_id

    def heartbeat(self, agent_id: str, pending_uploads: int = 0) -> None:
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not registered")
        self._agents[agent_id].last_seen = datetime.now(timezone.utc)
        self._agents[agent_id].pending_uploads = pending_uploads
        self._persist()

    def get(self, agent_id: str) -> AgentInfo | None:
        return self._agents.get(agent_id)

    def all(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def deregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._persist()

    def _persist(self) -> None:
        path = Path(settings.registry_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([a.to_dict() for a in self._agents.values()], indent=2)
        )

    def _load(self) -> None:
        path = Path(settings.registry_path)
        if not path.exists():
            return
        try:
            for d in json.loads(path.read_text()):
                agent = AgentInfo.from_dict(d)
                self._agents[agent.agent_id] = agent
        except (json.JSONDecodeError, KeyError):
            pass


registry = AgentRegistry()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd manager
pytest tests/test_registry.py -v
```

Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/registry.py manager/tests/test_registry.py
git commit -m "feat: add agent registry with in-memory store and JSON persistence"
```

---

## Task 4: Models and Auth

**Files:**
- Create: `manager/models.py`
- Create: `manager/auth.py`

No separate unit tests — these are validated through API tests in Tasks 5–7.

- [ ] **Step 1: Create `manager/models.py`**

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DeviceConfig(BaseModel):
    id: str
    ip: str
    hostname: Optional[str] = None
    snmp_version: str = "v3"
    username: str
    auth_protocol: str
    auth_password: str
    priv_protocol: str
    priv_password: str


class RegisterRequest(BaseModel):
    hostname: str
    ip: str


class RegisterResponse(BaseModel):
    agent_id: str
    devices: list[DeviceConfig]


class HeartbeatRequest(BaseModel):
    agent_id: str
    pending_uploads: int = 0
    poll_success_rate: float = 1.0


class AddDeviceRequest(BaseModel):
    ip: str
    hostname: Optional[str] = None
    username: str
    auth_protocol: str
    auth_password: str
    priv_protocol: str
    priv_password: str
    assigned_agent_id: Optional[str] = None


class DeviceResponse(BaseModel):
    id: str
    ip: str
    hostname: Optional[str]
    snmp_version: str
    username: str
    auth_protocol: str
    priv_protocol: str
    assigned_agent_id: Optional[str]
    created_at: datetime
    last_polled_at: Optional[datetime]
```

- [ ] **Step 2: Create `manager/auth.py`**

```python
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings

_bearer = HTTPBearer()


def require_api_key(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    if credentials.credentials != settings.manager_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return credentials.credentials
```

- [ ] **Step 3: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/models.py manager/auth.py
git commit -m "feat: add pydantic models and API key auth dependency"
```

---

## Task 5: Registration API

**Files:**
- Create: `manager/routers/registration.py`
- Create: `manager/tests/test_registration_api.py`
- Modify: `manager/main.py`

- [ ] **Step 1: Write failing tests**

Create `manager/tests/test_registration_api.py`:

```python
def test_register_returns_agent_id(client, auth_headers):
    resp = client.post("/register", json={"hostname": "nyc-01", "ip": "10.0.0.1"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"].startswith("nyc-01-")
    assert "devices" in data

def test_register_no_auth_returns_403(client):
    resp = client.post("/register", json={"hostname": "nyc-01", "ip": "10.0.0.1"})
    assert resp.status_code == 403

def test_register_wrong_key_returns_401(client):
    resp = client.post(
        "/register",
        json={"hostname": "nyc-01", "ip": "10.0.0.1"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert resp.status_code == 401

def test_heartbeat_updates_agent(client, auth_headers):
    reg = client.post("/register", json={"hostname": "nyc-02", "ip": "10.0.0.2"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    resp = client.post("/heartbeat", json={"agent_id": agent_id, "pending_uploads": 2}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

def test_heartbeat_unknown_agent_returns_404(client, auth_headers):
    resp = client.post("/heartbeat", json={"agent_id": "ghost", "pending_uploads": 0}, headers=auth_headers)
    assert resp.status_code == 404

def test_get_config_returns_devices(client, auth_headers, reset_db):
    reg = client.post("/register", json={"hostname": "nyc-03", "ip": "10.0.0.3"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    # Add a device assigned to this agent
    client.post("/devices", json={
        "ip": "192.168.1.1", "username": "admin",
        "auth_protocol": "SHA256", "auth_password": "authpass123",
        "priv_protocol": "AES256", "priv_password": "privpass123",
        "assigned_agent_id": agent_id
    }, headers=auth_headers)
    resp = client.get(f"/config/{agent_id}", headers=auth_headers)
    assert resp.status_code == 200
    devices = resp.json()
    assert len(devices) == 1
    assert devices[0]["ip"] == "192.168.1.1"

def test_get_config_unknown_agent_returns_404(client, auth_headers):
    resp = client.get("/config/ghost", headers=auth_headers)
    assert resp.status_code == 404

def test_list_agents_returns_registered(client, auth_headers):
    client.post("/register", json={"hostname": "nyc-04", "ip": "10.0.0.4"}, headers=auth_headers)
    resp = client.get("/agents", headers=auth_headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert any(a["hostname"] == "nyc-04" for a in agents)

def test_deregister_agent(client, auth_headers):
    reg = client.post("/register", json={"hostname": "nyc-05", "ip": "10.0.0.5"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    resp = client.delete(f"/agents/{agent_id}", headers=auth_headers)
    assert resp.status_code == 204
    agents = client.get("/agents", headers=auth_headers).json()
    assert not any(a["agent_id"] == agent_id for a in agents)

def test_deregister_unknown_agent_returns_404(client, auth_headers):
    resp = client.delete("/agents/ghost-id", headers=auth_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd manager
pytest tests/test_registration_api.py -v
```

Expected: errors — routers not yet created

- [ ] **Step 3: Create `manager/routers/registration.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from models import RegisterRequest, RegisterResponse, HeartbeatRequest, DeviceConfig
from registry import registry
from auth import require_api_key
from db import query

router = APIRouter(tags=["registration"])


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest, _: str = Depends(require_api_key)):
    agent_id = registry.register(req.hostname, req.ip)
    return RegisterResponse(agent_id=agent_id, devices=_devices_for(agent_id))


@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest, _: str = Depends(require_api_key)):
    try:
        registry.heartbeat(req.agent_id, req.pending_uploads)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent not registered")
    return {"ok": True}


@router.get("/config/{agent_id}", response_model=list[DeviceConfig])
def get_config(agent_id: str, _: str = Depends(require_api_key)):
    if not registry.get(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return _devices_for(agent_id)


@router.get("/agents")
def list_agents(_: str = Depends(require_api_key)):
    return [
        {
            "agent_id": a.agent_id,
            "hostname": a.hostname,
            "ip": a.ip,
            "status": a.status,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None,
            "pending_uploads": a.pending_uploads,
        }
        for a in registry.all()
    ]


@router.delete("/agents/{agent_id}", status_code=204)
def deregister_agent(agent_id: str, _: str = Depends(require_api_key)):
    if not registry.get(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    registry.deregister(agent_id)


def _devices_for(agent_id: str) -> list[DeviceConfig]:
    rows = query(
        "SELECT id, ip, hostname, snmp_version, username, auth_protocol, "
        "auth_password, priv_protocol, priv_password "
        "FROM devices WHERE assigned_agent_id = ?",
        [agent_id],
    )
    return [
        DeviceConfig(
            id=r[0], ip=r[1], hostname=r[2], snmp_version=r[3],
            username=r[4], auth_protocol=r[5], auth_password=r[6],
            priv_protocol=r[7], priv_password=r[8],
        )
        for r in rows
    ]
```

- [ ] **Step 4: Update `manager/main.py` to mount registration router**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import get_db, close_db
from routers import registration

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    yield
    close_db()

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(registration.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd manager
pytest tests/test_registration_api.py -v
```

Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/routers/registration.py manager/tests/test_registration_api.py manager/main.py
git commit -m "feat: add registration API (/register, /heartbeat, /config, /agents)"
```

---

## Task 6: Devices API

**Files:**
- Create: `manager/routers/devices.py`
- Create: `manager/tests/test_devices_api.py`
- Modify: `manager/main.py`

- [ ] **Step 1: Write failing tests**

Create `manager/tests/test_devices_api.py`:

```python
import pytest

DEVICE_PAYLOAD = {
    "ip": "10.1.1.1",
    "hostname": "sw-core-01",
    "username": "snmpv3user",
    "auth_protocol": "SHA256",
    "auth_password": "authpassword1",
    "priv_protocol": "AES256",
    "priv_password": "privpassword1",
}

def test_add_device_returns_201(client, auth_headers):
    resp = client.post("/devices", json=DEVICE_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["ip"] == "10.1.1.1"
    assert data["hostname"] == "sw-core-01"
    assert "id" in data
    assert "auth_password" not in data  # passwords not returned in response

def test_list_devices_returns_added(client, auth_headers):
    client.post("/devices", json=DEVICE_PAYLOAD, headers=auth_headers)
    resp = client.get("/devices", headers=auth_headers)
    assert resp.status_code == 200
    devices = resp.json()
    assert any(d["ip"] == "10.1.1.1" for d in devices)

def test_delete_device(client, auth_headers):
    add_resp = client.post("/devices", json=DEVICE_PAYLOAD, headers=auth_headers)
    device_id = add_resp.json()["id"]
    del_resp = client.delete(f"/devices/{device_id}", headers=auth_headers)
    assert del_resp.status_code == 204
    list_resp = client.get("/devices", headers=auth_headers)
    assert not any(d["id"] == device_id for d in list_resp.json())

def test_delete_nonexistent_returns_404(client, auth_headers):
    resp = client.delete("/devices/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404

def test_add_device_with_agent_assignment(client, auth_headers):
    reg = client.post("/register", json={"hostname": "ag-01", "ip": "10.0.0.1"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    payload = {**DEVICE_PAYLOAD, "assigned_agent_id": agent_id}
    resp = client.post("/devices", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["assigned_agent_id"] == agent_id

def test_config_only_returns_assigned_devices(client, auth_headers):
    reg = client.post("/register", json={"hostname": "ag-02", "ip": "10.0.0.2"}, headers=auth_headers)
    agent_id = reg.json()["agent_id"]
    # Device assigned to this agent
    client.post("/devices", json={**DEVICE_PAYLOAD, "ip": "10.1.1.2", "assigned_agent_id": agent_id}, headers=auth_headers)
    # Unassigned device
    client.post("/devices", json={**DEVICE_PAYLOAD, "ip": "10.1.1.3"}, headers=auth_headers)
    resp = client.get(f"/config/{agent_id}", headers=auth_headers)
    ips = [d["ip"] for d in resp.json()]
    assert "10.1.1.2" in ips
    assert "10.1.1.3" not in ips

def test_devices_no_auth_returns_403(client):
    resp = client.get("/devices")
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd manager
pytest tests/test_devices_api.py -v
```

Expected: errors — devices router not mounted

- [ ] **Step 3: Create `manager/routers/devices.py`**

```python
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from models import AddDeviceRequest, DeviceResponse
from auth import require_api_key
from db import query, execute

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
def list_devices(_: str = Depends(require_api_key)):
    rows = query(
        "SELECT id, ip, hostname, snmp_version, username, auth_protocol, "
        "priv_protocol, assigned_agent_id, created_at, last_polled_at FROM devices"
    )
    return [_to_response(r) for r in rows]


@router.post("", response_model=DeviceResponse, status_code=201)
async def add_device(req: AddDeviceRequest, _: str = Depends(require_api_key)):
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await execute(
        "INSERT INTO devices VALUES (?,?,?,'v3',?,?,?,?,?,?,?,NULL)",
        [
            device_id, req.ip, req.hostname, req.username,
            req.auth_protocol, req.auth_password,
            req.priv_protocol, req.priv_password,
            req.assigned_agent_id, now,
        ],
    )
    rows = query(
        "SELECT id, ip, hostname, snmp_version, username, auth_protocol, "
        "priv_protocol, assigned_agent_id, created_at, last_polled_at "
        "FROM devices WHERE id = ?",
        [device_id],
    )
    return _to_response(rows[0])


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, _: str = Depends(require_api_key)):
    if not query("SELECT id FROM devices WHERE id = ?", [device_id]):
        raise HTTPException(status_code=404, detail="Device not found")
    await execute("DELETE FROM devices WHERE id = ?", [device_id])


def _to_response(row: tuple) -> DeviceResponse:
    return DeviceResponse(
        id=row[0], ip=row[1], hostname=row[2], snmp_version=row[3],
        username=row[4], auth_protocol=row[5], priv_protocol=row[6],
        assigned_agent_id=row[7], created_at=row[8], last_polled_at=row[9],
    )
```

- [ ] **Step 4: Mount devices router in `manager/main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import get_db, close_db
from routers import registration, devices

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    yield
    close_db()

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(registration.router)
app.include_router(devices.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd manager
pytest tests/test_devices_api.py -v
```

Expected: 7 passed

- [ ] **Step 6: Run all tests to check for regressions**

```bash
cd manager
pytest tests/ -v
```

Expected: all passing

- [ ] **Step 7: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/routers/devices.py manager/tests/test_devices_api.py manager/main.py
git commit -m "feat: add devices API (add, list, delete)"
```

---

## Task 7: Ingest Service

**Files:**
- Create: `manager/services/ingest.py`
- Create: `manager/tests/test_ingest_service.py`

- [ ] **Step 1: Write failing tests**

Create `manager/tests/test_ingest_service.py`:

```python
import hashlib
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_parquet(tmp_path: Path, table: str) -> Path:
    if table == "snmp_polls":
        data = pa.table({
            "agent_id": pa.array(["a1"]),
            "device_ip": pa.array(["1.2.3.4"]),
            "oid": pa.array(["1.3.6.1.2.1.1.3.0"]),
            "value": pa.array(["100"]),
            "collected_at": pa.array([datetime.now(timezone.utc)], type=pa.timestamp("us", tz="UTC")),
        })
    else:
        data = pa.table({
            "agent_id": pa.array(["a1"]),
            "device_ip": pa.array(["1.2.3.4"]),
            "trap_oid": pa.array(["1.3.6.1.6.3.1.1.5.3"]),
            "varbinds": pa.array(['{"ifIndex":"1"}']),
            "received_at": pa.array([datetime.now(timezone.utc)], type=pa.timestamp("us", tz="UTC")),
        })
    path = tmp_path / f"{table}.parquet"
    pq.write_table(data, path)
    return path


@pytest.mark.asyncio
async def test_ingest_polls_success(reset_db, tmp_path):
    from services.ingest import ingest_file
    path = _make_parquet(tmp_path, "snmp_polls")
    sha = _sha256(path)
    count = await ingest_file("agent-01_1000_polls", sha, path, "snmp_polls")
    assert count == 1

@pytest.mark.asyncio
async def test_ingest_traps_success(reset_db, tmp_path):
    from services.ingest import ingest_file
    path = _make_parquet(tmp_path, "snmp_traps")
    sha = _sha256(path)
    count = await ingest_file("agent-01_1000_traps", sha, path, "snmp_traps")
    assert count == 1

@pytest.mark.asyncio
async def test_wrong_checksum_raises_and_dead_letters(reset_db, tmp_path):
    from services.ingest import ingest_file, ChecksumError
    import config
    path = _make_parquet(tmp_path, "snmp_polls")
    with pytest.raises(ChecksumError):
        await ingest_file("agent-01_1001_polls", "deadbeef" * 8, path, "snmp_polls")
    dl_dir = Path(config.settings.dead_letter_path)
    assert (dl_dir / "agent-01_1001_polls.parquet").exists()
    assert (dl_dir / "agent-01_1001_polls.error.json").exists()

@pytest.mark.asyncio
async def test_duplicate_file_id_raises(reset_db, tmp_path):
    from services.ingest import ingest_file, DuplicateFileError
    path = _make_parquet(tmp_path, "snmp_polls")
    sha = _sha256(path)
    await ingest_file("agent-01_1002_polls", sha, path, "snmp_polls")
    path2 = _make_parquet(tmp_path / "second", "snmp_polls")
    (tmp_path / "second").mkdir(exist_ok=True)
    path2 = _make_parquet(tmp_path, "snmp_polls")
    sha2 = _sha256(path2)
    with pytest.raises(DuplicateFileError):
        await ingest_file("agent-01_1002_polls", sha2, path2, "snmp_polls")

@pytest.mark.asyncio
async def test_tmp_file_deleted_after_success(reset_db, tmp_path):
    from services.ingest import ingest_file
    path = _make_parquet(tmp_path, "snmp_polls")
    sha = _sha256(path)
    await ingest_file("agent-01_1003_polls", sha, path, "snmp_polls")
    assert not path.exists()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd manager
pytest tests/test_ingest_service.py -v
```

Expected: `ImportError: No module named 'services.ingest'`

- [ ] **Step 3: Create `manager/services/ingest.py`**

```python
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from config import settings
from db import execute, query, ingest_parquet


class ChecksumError(Exception):
    pass


class DuplicateFileError(Exception):
    pass


async def ingest_file(
    file_id: str, claimed_sha256: str, tmp_path: Path, table: str
) -> int:
    actual_sha256 = _sha256(tmp_path)
    if actual_sha256 != claimed_sha256.lower():
        _dead_letter(file_id, tmp_path, f"SHA256 mismatch: got {actual_sha256}")
        raise ChecksumError("SHA256 mismatch")

    if query("SELECT file_id FROM ingest_log WHERE file_id = ?", [file_id]):
        tmp_path.unlink(missing_ok=True)
        raise DuplicateFileError(f"Already ingested: {file_id}")

    try:
        row_count = await ingest_parquet(table, str(tmp_path))
        await execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?)",
            [file_id, datetime.now(timezone.utc), row_count],
        )
        return row_count
    except Exception as exc:
        _dead_letter(file_id, tmp_path, str(exc))
        raise
    finally:
        tmp_path.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _dead_letter(file_id: str, src: Path, error: str) -> None:
    dl_dir = Path(settings.dead_letter_path)
    dl_dir.mkdir(parents=True, exist_ok=True)
    dest = dl_dir / f"{file_id}.parquet"
    if src.exists():
        shutil.move(str(src), dest)
    (dl_dir / f"{file_id}.error.json").write_text(
        json.dumps({
            "file_id": file_id,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, indent=2)
    )
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd manager
pytest tests/test_ingest_service.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/services/ingest.py manager/tests/test_ingest_service.py
git commit -m "feat: add ingest service with SHA256 verify, dedup, and dead-letter"
```

---

## Task 8: Ingest API

**Files:**
- Create: `manager/routers/ingest.py`
- Create: `manager/tests/test_ingest_api.py`
- Modify: `manager/main.py`

- [ ] **Step 1: Write failing tests**

Create `manager/tests/test_ingest_api.py`:

```python
import hashlib
import pytest
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_ingest_polls_success(client, auth_headers, sample_polls_parquet):
    sha = _sha256(sample_polls_parquet)
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "agent-01_1000_polls", "x-sha256": sha},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 5

def test_ingest_traps_success(client, auth_headers, sample_traps_parquet):
    sha = _sha256(sample_traps_parquet)
    with open(sample_traps_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "agent-01_1000_traps", "x-sha256": sha},
            files={"file": ("traps.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 3

def test_ingest_wrong_checksum_returns_400(client, auth_headers, sample_polls_parquet):
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "agent-01_1001_polls", "x-sha256": "bad" * 20},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 400

def test_ingest_duplicate_is_idempotent(client, auth_headers, sample_polls_parquet, tmp_path):
    import pyarrow as pa, pyarrow.parquet as pq
    from datetime import datetime, timezone
    sha = _sha256(sample_polls_parquet)
    for _ in range(2):
        # Re-open file each time (first upload consumes the stream)
        with open(sample_polls_parquet, "rb") as f:
            resp = client.post(
                "/ingest",
                headers={**auth_headers, "x-file-id": "agent-01_1002_polls", "x-sha256": sha},
                files={"file": ("polls.parquet", f, "application/octet-stream")},
            )
        assert resp.status_code == 200
    # Only 5 rows total, not 10
    from db import query
    count = query("SELECT COUNT(*) FROM snmp_polls")[0][0]
    assert count == 5

def test_ingest_invalid_file_id_format_returns_400(client, auth_headers, sample_polls_parquet):
    sha = _sha256(sample_polls_parquet)
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "badformat", "x-sha256": sha},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 400

def test_ingest_no_auth_returns_403(client, sample_polls_parquet):
    sha = _sha256(sample_polls_parquet)
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={"x-file-id": "agent-01_1003_polls", "x-sha256": sha},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd manager
pytest tests/test_ingest_api.py -v
```

Expected: errors — ingest router not mounted

- [ ] **Step 3: Create `manager/routers/ingest.py`**

```python
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from auth import require_api_key
from services.ingest import ChecksumError, DuplicateFileError, ingest_file

router = APIRouter(tags=["ingest"])

_VALID_TYPES = {"polls": "snmp_polls", "traps": "snmp_traps"}


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    x_file_id: str = Header(...),
    x_sha256: str = Header(...),
    _: str = Depends(require_api_key),
):
    parts = x_file_id.rsplit("_", 1)
    if len(parts) != 2 or parts[1] not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid file_id: {x_file_id}")

    table = _VALID_TYPES[parts[1]]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        rows = await ingest_file(x_file_id, x_sha256, tmp_path, table)
        return {"ok": True, "rows_ingested": rows}
    except ChecksumError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DuplicateFileError:
        return {"ok": True, "rows_ingested": 0, "duplicate": True}
```

- [ ] **Step 4: Mount ingest router in `manager/main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import get_db, close_db
from routers import registration, devices, ingest

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    yield
    close_db()

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(registration.router)
app.include_router(devices.router)
app.include_router(ingest.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run all tests — verify everything passes**

```bash
cd manager
pytest tests/ -v
```

Expected: all tests passing (25+)

- [ ] **Step 6: Commit**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
git add manager/routers/ingest.py manager/tests/test_ingest_api.py manager/main.py
git commit -m "feat: add ingest API endpoint (POST /ingest)"
```

---

## Task 9: Dockerfile and docker-compose

**Files:**
- Create: `manager/Dockerfile`
- Create: `docker-compose.yml` (project root)
- Create: `manager/.env.example`

- [ ] **Step 1: Create `manager/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/db /data/registry /data/dead-letter

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `docker-compose.yml` at project root**

```yaml
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
      - MANAGER_API_KEY=${MANAGER_API_KEY:-change-me-in-production}
      - DB_PATH=/data/db/metrics.db
      - REGISTRY_PATH=/data/registry/registry.json
      - DEAD_LETTER_PATH=/data/dead-letter
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

- [ ] **Step 3: Build and verify container starts**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
docker-compose build
docker-compose up -d
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Stop container**

```bash
docker-compose down
```

- [ ] **Step 5: Commit**

```bash
git add manager/Dockerfile docker-compose.yml manager/.env.example
git commit -m "feat: add manager Dockerfile and docker-compose"
```

---

## Final Check: Run Full Test Suite

- [ ] **Run all manager tests**

```bash
cd manager
pytest tests/ -v --tb=short
```

Expected: all tests passing, 0 failures

- [ ] **Build Docker image clean**

```bash
cd /Users/emmanuelpoe/Documents/dev-projects/snmp-collector
docker build manager/ --no-cache -t snmp-manager:latest
```

Expected: build succeeds with no errors

- [ ] **Commit final plan-1 tag**

```bash
git tag plan-1-complete
git push origin main --tags
```

---

## What's Next

- **Plan 2:** Go Agent — polling worker pool, trap listener, Parquet buffer, offload worker, health endpoint
- **Plan 3:** Web UI — Jinja2 + HTMX + Tailwind dark theme (dashboard, agents, devices, query pages)
- **Plan 4:** Dev environment (docker-compose.dev.yml, snmpsim, trap-gen) + E2E tests + README
