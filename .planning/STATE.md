# STATE.md

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-02)

**Core value:** Operators can deploy agents that autonomously collect SNMP metrics from devices and view those metrics in the frontend.
**Current focus:** Phase 1 — Backend Foundation

## Current Position

- **Phase:** 1 of 5 — Backend Foundation
- **Plan:** Not started
- **Status:** Ready to plan

## Progress

`[░░░░░░░░░░] 0%`

## Recent Decisions

- Agent-based collection model approved (2026-05-02)
- Parquet pre-parsed with interface_name/oid_name (avoid OID translation at query time)
- Backend mounts DuckDB read-only via file mount (no extra HTTP hop)
- Postgres metrics tables hard-dropped (no prod data to preserve)

## Pending Todos

(none)

## Blockers / Concerns

(none)

## Session Continuity

Last session: 2026-05-02
Stopped at: Project initialized. Ready to plan Phase 1.
Resume file: none
