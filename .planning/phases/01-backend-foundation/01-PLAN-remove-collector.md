---
phase: 1
plan: 1.2
title: "Remove collector + Prometheus, add internal endpoints"
wave: 2
depends_on: [1.1]
autonomous: true
files_modified:
  - backend/main.py
  - backend/config.py
  - backend/routers/devices.py
  - backend/schemas.py
  - backend/services/collector.py
  - backend/services/prometheus.py
  - docker-compose.yml
requirements:
  - BE-02
  - BE-03
  - BE-05
  - BE-07
  - BE-08
must_haves:
  goal: "collector.py and prometheus.py deleted, main.py runs without background task, two new endpoints live"
  truths:
    - "GET /internal/devices?agent_id=X returns JSON array of device objects for that agent, no auth required"
    - "GET /agents proxies the manager's GET /agents response and returns it verbatim"
    - "Backend starts without importing or referencing services/collector.py or services/prometheus.py"
    - "docker-compose.yml backend service has volume mount ./data/db:/data/db:ro"
    - "docker-compose.yml backend service has MANAGER_URL environment variable set to http://manager:8000"
    - "config.py has manager_url setting"
---

<objective>
Delete `services/collector.py` and `services/prometheus.py`. Gut `main.py` of the background collection task and its import. Add `GET /internal/devices?agent_id=X` to a new `routers/internal.py` router. Add `GET /agents` to a new `routers/agents.py` router that proxies the manager. Wire both routers into `main.py`. Update `config.py` with `manager_url`. Update `docker-compose.yml` with the DuckDB volume mount and `MANAGER_URL` env var.

Purpose: The agent-based architecture eliminates direct SNMP polling. The backend must instead serve device config to agents (via manager) and proxy agent status to the frontend.

Output:
- `backend/services/collector.py` — deleted
- `backend/services/prometheus.py` — deleted
- `backend/main.py` — lifespan removed, new routers wired
- `backend/config.py` — manager_url added
- `backend/routers/internal.py` — new file with GET /internal/devices
- `backend/routers/agents.py` — new file with GET /agents
- `backend/schemas.py` — DeviceInternalResponse schema added
- `docker-compose.yml` — backend volume and env updated
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<interfaces>
<!-- Manager service internal Docker hostname: manager (from docker-compose.yml service name) -->
<!-- Manager listens on port 8000 inside Docker network: docker-compose.yml maps 8001:8000 -->
<!-- Manager GET /agents endpoint: returns agent list (exact shape determined by manager implementation) -->
<!-- Backend runs on snmp-network Docker network — can reach http://manager:8000 -->

<!-- Device model columns after Plan 1.1: id, name, ip_address, snmp_version, snmp_community, snmp_port, -->
<!--   snmp_modules, device_type, description, enabled, created_at, updated_at, username, auth_protocol, -->
<!--   auth_password, priv_protocol, priv_password, assigned_agent_id -->

<!-- config.py Settings class uses pydantic_settings BaseSettings with env_file=".env" -->
<!-- New setting needed: manager_url: str = "http://manager:8000" -->

<!-- /internal/devices query param: agent_id (str) — filter devices WHERE assigned_agent_id = agent_id -->
<!-- No authentication on /internal/devices — it is an internal service-to-service endpoint -->
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Delete services, gut main.py, update config.py</name>
  <files>backend/services/collector.py, backend/services/prometheus.py, backend/main.py, backend/config.py</files>
  <read_first>
    - backend/main.py — read before editing; must see exact import lines and lifespan function to remove
    - backend/config.py — read before editing; must see existing Settings fields and model_post_init
    - backend/services/collector.py — confirm it exists before deletion
    - backend/services/prometheus.py — confirm it exists before deletion
  </read_first>
  <action>
**Step 1 — Delete both service files:**
Delete `backend/services/collector.py` and `backend/services/prometheus.py`. These files are entirely replaced by the agent model. No code from them is reused.

**Step 2 — Rewrite backend/main.py:**
Remove:
- `import asyncio` (no longer needed)
- `from services.collector import run_scheduled_collection`
- The entire `@asynccontextmanager async def lifespan(app: FastAPI):` function (lines 19–38)
- The `lifespan=lifespan` argument from the `FastAPI(...)` constructor

Add two new router imports:
```python
from routers import devices, metrics, config, internal, agents
```

Add two new `app.include_router(...)` calls:
```python
app.include_router(internal.router)
app.include_router(agents.router)
```

The final main.py should look like:
```python
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import devices, metrics, config, internal, agents

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API for collecting and managing SNMP metrics from network devices",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router)
app.include_router(metrics.router)
app.include_router(config.router)
app.include_router(internal.router)
app.include_router(agents.router)


@app.get("/")
def root():
    return {
        "message": "SNMP Metrics Collector API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "snmp-collector-api"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Step 3 — Update backend/config.py:**
Add one field to the `Settings` class after `default_collection_interval`:
```python
# Manager service URL
manager_url: str = "http://manager:8000"
```

Also remove these two settings that are now unused (Prometheus/collector specific):
- `snmp_exporter_url: str = "http://snmp-exporter:9116"`
- `prometheus_config_path: str = "/app/prometheus_config/snmp.yml"`
- `default_collection_interval: int = 60`

Leave `database_url`, `postgres_*`, `api_title`, `api_version` unchanged.
  </action>
  <verify>
    <automated>test ! -f backend/services/collector.py && test ! -f backend/services/prometheus.py && echo "files deleted ok"</automated>
  </verify>
  <done>
    - `backend/services/collector.py` does not exist
    - `backend/services/prometheus.py` does not exist
    - `backend/main.py` has no import of `run_scheduled_collection`
    - `backend/main.py` has no `asynccontextmanager` or `lifespan` function
    - `backend/main.py` imports `internal` and `agents` from routers
    - `backend/config.py` has `manager_url: str = "http://manager:8000"` field
    - `backend/config.py` has no `snmp_exporter_url` or `prometheus_config_path` fields
  </done>
</task>

<task type="auto">
  <name>Task 2: Create internal and agents routers, update docker-compose</name>
  <files>backend/routers/internal.py, backend/routers/agents.py, backend/schemas.py, docker-compose.yml</files>
  <read_first>
    - backend/routers/devices.py — read to understand existing router pattern (prefix, tags, Depends(get_db), query style)
    - backend/database.py — read to confirm get_db signature
    - backend/schemas.py — read before adding new schema; must append without breaking existing schemas
    - docker-compose.yml — read before editing; must see exact backend service block
  </read_first>
  <action>
**Step 1 — Create backend/routers/internal.py:**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Device
from schemas import DeviceInternalResponse

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/devices", response_model=List[DeviceInternalResponse])
def get_devices_for_agent(
    agent_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Return devices assigned to a given agent. No auth required (internal service endpoint)."""
    query = db.query(Device).filter(Device.enabled == True)
    if agent_id is not None:
        query = query.filter(Device.assigned_agent_id == agent_id)
    return query.all()
```

**Step 2 — Create backend/routers/agents.py:**

```python
import httpx
import logging
from fastapi import APIRouter, HTTPException
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def get_agents():
    """Proxy the manager's /agents response to the frontend."""
    url = f"{settings.manager_url}/agents"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = client.get(url)  # synchronous-style but inside async def
            # Use await for true async:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to reach manager at {url}: {e}")
        raise HTTPException(status_code=502, detail="Manager unreachable")
```

Wait — write it cleanly without the duplicate block:

```python
import httpx
import logging
from fastapi import APIRouter, HTTPException
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def get_agents():
    """Proxy the manager's /agents response to the frontend."""
    url = f"{settings.manager_url}/agents"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to reach manager at {url}: {e}")
        raise HTTPException(status_code=502, detail="Manager unreachable")
```

**Step 3 — Add DeviceInternalResponse to backend/schemas.py:**

Append after the existing `DeviceResponse` class (do not modify existing schemas):

```python
class DeviceInternalResponse(BaseModel):
    """Schema for /internal/devices — fields agents need for SNMP polling"""
    id: int
    name: str
    ip_address: str
    snmp_version: str
    snmp_community: str
    snmp_port: int
    snmp_modules: List[str]
    enabled: bool
    assigned_agent_id: Optional[str] = None
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None
    priv_password: Optional[str] = None

    class Config:
        from_attributes = True
```

**Step 4 — Update docker-compose.yml backend service:**

In the `backend:` service block:
1. Add volume `./data/db:/data/db:ro` to the `volumes:` list (alongside existing `./backend:/app` and `./prometheus:/app/prometheus_config`)
2. Add environment variable `MANAGER_URL: http://manager:8000` to the `environment:` block
3. Remove `snmp-exporter` from `depends_on` (backend no longer calls snmp-exporter)
4. Remove the `SNMP_EXPORTER_URL` and `PROMETHEUS_CONFIG_PATH` env vars

The updated backend service block should be:
```yaml
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: snmp-backend
    environment:
      DATABASE_URL: ${DATABASE_URL:-}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_PORT: ${POSTGRES_PORT:-5432}
      POSTGRES_HOST: postgres
      MANAGER_URL: http://manager:8000
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    volumes:
      - ./backend:/app
      - ./data/db:/data/db:ro
    networks:
      - snmp-network
    depends_on:
      postgres:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
  </action>
  <verify>
    <automated>python -c "
import ast
for f in ['backend/routers/internal.py', 'backend/routers/agents.py']:
    ast.parse(open(f).read())
    print(f, 'syntax ok')
" && grep -c 'data/db:/data/db:ro' docker-compose.yml && grep -c 'MANAGER_URL' docker-compose.yml</automated>
  </verify>
  <done>
    - `backend/routers/internal.py` exists with `router = APIRouter(prefix="/internal", ...)` and `GET /devices` handler
    - `backend/routers/agents.py` exists with `router = APIRouter(prefix="/agents", ...)` and `GET ""` handler
    - `backend/schemas.py` contains `class DeviceInternalResponse(BaseModel)` with `assigned_agent_id`, `username`, `auth_protocol`, `auth_password`, `priv_protocol`, `priv_password` fields
    - `docker-compose.yml` backend volumes list contains `./data/db:/data/db:ro`
    - `docker-compose.yml` backend environment contains `MANAGER_URL: http://manager:8000`
    - `docker-compose.yml` backend `depends_on` does not list `snmp-exporter`
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| manager → /internal/devices | Manager calls this endpoint without auth; endpoint is internal-only |
| backend → manager /agents | Backend proxies manager response to frontend; manager is trusted internal service |
| frontend → /agents | Frontend receives proxied manager data |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1.2-01 | Elevation of Privilege | GET /internal/devices (no auth) | accept | Endpoint is on internal Docker network only; not exposed to public; operator controls network isolation |
| T-1.2-02 | Spoofing | GET /agents proxy | accept | Manager is a trusted internal service on snmp-network; no external path to manager:8000 |
| T-1.2-03 | Denial of Service | agents.py httpx call blocks on manager timeout | mitigate | httpx.AsyncClient timeout=10.0 already set; FastAPI will return 502 on timeout |
</threat_model>

<verification>
```bash
# Verify deleted files are gone
test ! -f backend/services/collector.py && echo "collector deleted"
test ! -f backend/services/prometheus.py && echo "prometheus deleted"

# Verify no stale references to deleted modules in main.py
grep -v 'collector\|prometheus' backend/main.py | grep -c 'import' || true

# Verify new routers exist
test -f backend/routers/internal.py && echo "internal router ok"
test -f backend/routers/agents.py && echo "agents router ok"

# Verify docker-compose has required changes
grep 'data/db:/data/db:ro' docker-compose.yml && echo "volume mount ok"
grep 'MANAGER_URL' docker-compose.yml && echo "MANAGER_URL ok"

# Verify schemas has DeviceInternalResponse
grep -c 'class DeviceInternalResponse' backend/schemas.py
```
</verification>

<success_criteria>
- `services/collector.py` and `services/prometheus.py` do not exist
- `main.py` has no lifespan function, no asyncio import, no collector import
- `GET /internal/devices?agent_id=X` route defined in routers/internal.py
- `GET /agents` route defined in routers/agents.py, proxies `settings.manager_url + /agents`
- `config.py` has `manager_url = "http://manager:8000"`
- `docker-compose.yml` backend has `./data/db:/data/db:ro` volume and `MANAGER_URL` env var
</success_criteria>

<output>
After completion, create `.planning/phases/01-backend-foundation/01-1.2-SUMMARY.md`
</output>
