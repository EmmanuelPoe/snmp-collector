# SNMP Collector — Manager Integration

## What This Is

An SNMP monitoring platform transitioning from direct backend polling to a distributed agent-based model. Agents collect SNMP data and upload parquet files to the manager service; the backend becomes a read-only UI API layer. The frontend gains an Agents tab for operational visibility.

## Core Value

Operators can deploy agents that autonomously collect SNMP metrics from devices and view those metrics in the frontend — without the backend directly touching devices.

## Requirements

### Validated

- ✓ Backend serves device CRUD via Postgres — existing
- ✓ Frontend displays devices and metrics via backend API — existing
- ✓ Manager receives parquet uploads with deduplication and dead-letter queue — existing
- ✓ Manager authenticates agents with API keys — existing

### Active

- [ ] Backend extended with v3 SNMP fields and `assigned_agent_id` on devices table
- [ ] Backend exposes `GET /internal/devices?agent_id=X` for manager → agent config
- [ ] Backend exposes `GET /agents` proxying manager's agent list to frontend
- [ ] Backend metrics queries read from DuckDB (not Postgres snmp_metrics tables)
- [ ] Backend direct SNMP polling removed
- [ ] Manager fetches device config from backend (not own DuckDB)
- [ ] Manager snmp_polls schema extended with `interface_name` and `oid_name`
- [ ] Agent service polls devices via SNMP, buffers, and uploads structured parquet
- [ ] Agent retries failed uploads with exponential backoff, discards after 1 hour
- [ ] Frontend Agents tab shows agent health (status, last_seen, pending_uploads)
- [ ] Frontend device form includes optional v3 credential fields and agent assignment
- [ ] Docker Compose wires agent, manager, backend with correct deps and volumes

### Out of Scope

- Multi-region agent deployment — not needed for initial integration
- Agent authentication beyond API key — network isolation is sufficient
- Prometheus scraping for collection — removed (agent model replaces it)
- Preserving existing snmp_metrics/if_mib_metrics Postgres data — active dev, no production data

## Context

- **Design spec:** `docs/superpowers/specs/2026-05-02-manager-integration-design.md` — fully approved
- **Backend:** FastAPI + Postgres (Alembic migrations), port 8000
- **Manager:** FastAPI + DuckDB, port 8001, already handles parquet ingest with dedup
- **Frontend:** React SPA, targets backend port 8000
- **Data flow:** Agent → Manager (parquet) → DuckDB → Backend (read-only mount) → Frontend

## Constraints

- **Stack**: Python (backend/manager/agent), React (frontend), DuckDB, Postgres, Docker Compose
- **DuckDB access**: Backend mounts DuckDB read-only; only manager writes
- **Auth**: No auth between manager and backend (same Docker network)
- **Agent upload trigger**: 500 rows OR 60s elapsed (dual threshold)
- **Retry**: Exponential backoff 1s→5min max, discard after 1 hour

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agent-based collection | Distributed collection, decouples backend from SNMP | — Pending |
| Backend reads DuckDB directly (file mount) | No extra HTTP hop; DuckDB safe for concurrent reads | — Pending |
| Postgres metrics tables hard-dropped | Active dev, no production data to preserve | — Pending |
| No manager↔backend auth | Same Docker network; network isolation sufficient | — Pending |
| Parquet pre-parsed (interface_name, oid_name) | Avoid OID translation cost at query time | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

---
*Last updated: 2026-05-02 after initialization*
