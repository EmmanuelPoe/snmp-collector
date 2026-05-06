# Enterprise Deployment Design
**Date:** 2026-05-05
**Scope:** Production-grade hardening of the snmp-collector Docker Compose stack
**Target:** Single-server Docker Compose deployment

---

## Goals

Transform the current development-oriented stack into a production-deployable system with:
1. JWT-based authentication with role-based access control
2. Production Docker builds with nginx reverse proxy
3. Full observability stack (Prometheus + Grafana + Loki + Promtail)

Out of scope: CI/CD, Kubernetes, multi-tenancy, horizontal scaling.

---

## Section 1: Authentication & Authorization

### Database

New `users` table in PostgreSQL (managed via Alembic migration):

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| email | String(255) unique | login identifier |
| hashed_password | String(255) | bcrypt |
| role | Enum | `admin`, `editor`, `viewer` |
| is_active | Boolean | default true |
| created_at | DateTime | server default |

### Backend

**New dependencies:** `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`

**New files:**
- `backend/routers/auth.py` — three endpoints:
  - `POST /auth/register` — admin-only, creates a new user
  - `POST /auth/login` — accepts `email` + `password` (form data), returns `{ access_token, token_type }`
  - `GET /auth/me` — returns current user profile
- `backend/auth.py` — `get_current_user(token)` dependency; `require_role(role)` dependency factory

**New env vars:**
- `JWT_SECRET` — required, no default (startup fails if missing)
- `JWT_ALGORITHM` — default `HS256`
- `JWT_EXPIRE_HOURS` — default `8`
- `FRONTEND_URL` — used to lock down CORS (replaces `allow_origins=["*"]`)

**Internal router auth:**
The `/internal` router is called by the manager (service-to-service), not by users. It must NOT use JWT auth — instead protect it with `MANAGER_API_KEY` bearer auth (same pattern as the manager's own auth). This also closes the current vulnerability where it exposes plaintext SNMP v3 credentials to any unauthenticated caller.

Add a `require_manager_key` dependency to `backend/routers/internal.py` that validates `Authorization: Bearer <MANAGER_API_KEY>` (read from `settings.manager_api_key`). The manager already sends this header when calling `/internal/devices`.

**Role enforcement on existing routes:**

| Router | Admin | Editor | Viewer |
|---|---|---|---|
| `GET /devices`, `GET /metrics` | ✓ | ✓ | ✓ |
| `POST /devices`, `PUT /devices` | ✓ | ✓ | ✗ |
| `DELETE /devices` | ✓ | ✗ | ✗ |
| `GET /config` | ✓ | ✓ | ✓ |
| `PUT /config` | ✓ | ✓ | ✗ |
| `GET /agents` | ✓ | ✓ | ✓ |
| `POST /auth/register` | ✓ | ✗ | ✗ |

**Seed user:** On startup, if the `users` table is empty, create `admin@localhost` / `admin` with role `admin`. Log a `WARNING: default admin credentials are active — change immediately`.

**CORS:** Replace `allow_origins=["*"]` with `allow_origins=[settings.frontend_url]`.

### Frontend

**New dependencies:** none (axios already present)

**New files/components:**
- `frontend/src/pages/LoginPage.js` — email + password form, calls `POST /api/auth/login`, stores JWT in `localStorage`
- `frontend/src/hooks/useAuth.js` — reads token from localStorage, provides `user`, `login()`, `logout()`
- `frontend/src/components/PrivateRoute.js` — redirects to `/login` if no valid token

**Modified files:**
- `frontend/src/services/api.js` — add axios request interceptor to attach `Authorization: Bearer <token>` header; add response interceptor to redirect to `/login` on 401
- `frontend/src/App.js` — wrap all existing routes in `PrivateRoute`; add `/login` route

**No self-registration UI** — admin creates users via `POST /auth/register` (API only). This keeps the frontend simple.

---

## Section 2: Production Docker Hardening + Nginx

### Production Dockerfiles

**backend/Dockerfile:**
- Remove dev stage. Single production stage.
- `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]` (no `--reload`)
- No source volume mount in production compose

**frontend/Dockerfile:**
- Multi-stage: `node:20-alpine` build stage runs `npm ci && npm run build`
- Final stage: `nginx:alpine` copies `/app/build` to `/usr/share/nginx/html`
- Replaces the current dev Dockerfile that runs `npm start`

**manager/Dockerfile:**
- Remove any dev flags. Run with `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1` (DuckDB is single-writer, 1 worker is correct)

**agent/Dockerfile:** No changes needed.

### Nginx

**New directory:** `nginx/`
- `nginx/nginx.conf` — main config
- `nginx/conf.d/default.conf` — routing rules

**Routing:**

| Path | Upstream | Notes |
|---|---|---|
| `/` | frontend container | serves React static build |
| `/api/` | backend:8000 | strips `/api` prefix |
| `/health` | backend:8000/health | for external uptime checks |

Manager is NOT proxied publicly. Agents communicate with manager directly on the Docker internal network (`http://manager:8000`). If agents run outside Docker, expose `manager` port `8001` as needed.

**Public ports after hardening:**
- `80` — nginx only (all app traffic)
- `8001` — manager (agents only, can be firewalled to agent IPs)
- `5432` — postgres (should be firewalled, internal only)

### docker-compose.yml changes

- Add `nginx` service, expose port `80`
- Remove port exposure from `backend` and `frontend` (internal only)
- Remove `./backend:/app` and `./frontend/src:/app/src` volume mounts
- Add `target: production` to frontend build
- Add `FRONTEND_URL`, `JWT_SECRET` to backend environment
- Add `NODE_ENV=production` and `REACT_APP_API_URL=/api` to frontend build args

---

## Section 3: Observability Stack

### New file: docker-compose.observability.yml

Four services, all joining `snmp-network`:

**Prometheus** (port `9090`, internal only):
- Scrapes backend and manager `/metrics` endpoints every 15s
- Config: `observability/prometheus/prometheus.yml`
- Persistent volume: `prometheus_data`

**Grafana** (proxied via nginx at `/grafana/` or direct port `3001`):
- Pre-provisioned datasources: Prometheus + Loki
- Pre-built SNMP collection dashboard (provisioned via `observability/grafana/dashboards/`)
- Dashboard panels:
  - Active agents (gauge)
  - Polls per minute (time series)
  - Ingest rows per minute (time series)
  - HTTP error rate by service (time series)
  - DuckDB file size (stat)
  - Agent heartbeat lag (table)
- Credentials: `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` env vars
- Persistent volume: `grafana_data`

**Loki** (internal only):
- Log aggregation backend
- Config: `observability/loki/loki-config.yml`
- Persistent volume: `loki_data`

**Promtail** (no exposed ports):
- Mounts `/var/lib/docker/containers` read-only
- Ships logs from all containers to Loki
- Labels: `container`, `service`, `level` (parsed from JSON logs)
- Config: `observability/promtail/promtail-config.yml`

### Application changes

**Structured JSON logging** added to backend, manager, and agent:

Replace `logging.basicConfig(...)` with a JSON log formatter. Each log line becomes:
```json
{ "time": "...", "level": "INFO", "service": "backend", "message": "...", "router": "devices" }
```

**Prometheus instrumentation:**
- Add `prometheus-fastapi-instrumentator` to `backend/requirements.txt` and `manager/requirements.txt`
- One line in each `main.py`: `Instrumentator().instrument(app).expose(app)`
- Exposes standard HTTP metrics: request count, latency histograms, error rates

### Makefile additions

```makefile
up-full:        ## Start core stack + observability
down-full:      ## Stop core stack + observability
logs-grafana:   ## Tail grafana logs
logs-loki:      ## Tail loki logs
logs-promtail:  ## Tail promtail logs
```

---

## New Environment Variables Summary

| Variable | Service | Required | Default | Notes |
|---|---|---|---|---|
| `JWT_SECRET` | backend | yes | none | startup fails if missing |
| `JWT_ALGORITHM` | backend | no | `HS256` | |
| `JWT_EXPIRE_HOURS` | backend | no | `8` | |
| `FRONTEND_URL` | backend | no | `http://localhost` | used for CORS |
| `GF_SECURITY_ADMIN_USER` | grafana | no | `admin` | |
| `GF_SECURITY_ADMIN_PASSWORD` | grafana | yes | none | |

---

## File Changes Summary

### New files
- `nginx/nginx.conf`
- `nginx/conf.d/default.conf`
- `docker-compose.observability.yml`
- `observability/prometheus/prometheus.yml`
- `observability/grafana/provisioning/datasources/datasources.yml`
- `observability/grafana/provisioning/dashboards/dashboard.yml`
- `observability/grafana/dashboards/snmp-collection.json`
- `observability/loki/loki-config.yml`
- `observability/promtail/promtail-config.yml`
- `backend/routers/auth.py`
- `backend/auth.py`
- `backend/alembic/versions/008_add_users.py`
- `frontend/src/pages/LoginPage.js`
- `frontend/src/hooks/useAuth.js`
- `frontend/src/components/PrivateRoute.js`

### Modified files
- `backend/Dockerfile` — production build
- `backend/main.py` — add auth router, CORS fix, JSON logging
- `backend/config.py` — add JWT_SECRET, FRONTEND_URL
- `backend/models.py` — add User model
- `backend/requirements.txt` — add jose, passlib, prometheus-fastapi-instrumentator
- `backend/routers/devices.py`, `metrics.py`, `config.py`, `agents.py` — add JWT auth dependencies
- `backend/routers/internal.py` — add MANAGER_API_KEY bearer auth dependency
- `frontend/Dockerfile` — multi-stage production build
- `frontend/src/App.js` — add PrivateRoute, login route
- `frontend/src/services/api.js` — add auth interceptors
- `manager/Dockerfile` — production build
- `manager/main.py` — JSON logging, prometheus instrumentation
- `manager/requirements.txt` — add prometheus-fastapi-instrumentator
- `docker-compose.yml` — nginx service, remove dev mounts, add env vars
- `Makefile` — add up-full, down-full, observability log targets
- `.env.example` — add JWT_SECRET, FRONTEND_URL, GF_SECURITY_ADMIN_PASSWORD

---

## Implementation Order

1. **Auth backend** (users model, migration, auth router, role dependencies on all routes)
2. **Auth frontend** (login page, interceptors, PrivateRoute)
3. **Production Dockerfiles** (backend, frontend multi-stage, manager)
4. **Nginx** (config + service in docker-compose)
5. **Structured logging** (backend, manager, agent)
6. **Prometheus instrumentation** (backend + manager)
7. **Observability compose** (Loki, Promtail, Prometheus, Grafana with provisioning)
8. **Makefile + .env.example** updates
