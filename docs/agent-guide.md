# Agent guide

Read `CLAUDE.md` first (commands, services, constraints). The implementation plan (`docs/implementation-plan.md`) records conventions used for every step so far; follow them.

## Recipes

**Add a backend endpoint**
1. Pick the router in `backend/routers/` (or add one and include it in `backend/main.py`).
2. Pydantic schemas for request/response; never include credential fields in general responses.
3. Auth dependency: `get_current_user`, `require_role("editor", "admin")` or `require_role("admin")`.
4. Write an audit entry for security-relevant changes.
5. Tests in `backend/tests/` (auth cases + behavior). Add the client call to `frontend/src/services/api.js`.
6. Document it in the README API reference.

**Change the Postgres schema**: add an Alembic revision numbered after the newest file in `backend/alembic/versions/`, update `backend/models.py`, run `make migrate`, and cover it in tests. Never edit an existing revision.

**Add a metric or OID**: collection is driven by the OID whitelist (`CollectionConfig`, `config` router) and the agent's `snmp.py`; rows land in DuckDB `snmp_polls` via the manager's ingest. Queries go in the backend `metrics` router (read-only DuckDB, keyed by `device_ip`).

**Add an alert type**: extend `backend/alert_evaluator.py` (runs every 30 s), add the type to the model/enum with a migration if needed, and add tests to `test_alert_evaluator.py`.

**Add a UI page**: component under `frontend/src/components/` (or `pages/`), route in `App.js`, entry in `navConfig.js`, data via `usePolledResource`/`services/api.js`, a `*.test.js`, then rebuild the frontend container.

**Change shared code**: edit `shared/`, run `python scripts/sync_shared.py`, commit all copies.

**Add or rotate a secret**: support `NAME` and `NAME_FILE`, validate at startup, add to `.env.example`, `docker-compose.prod.yml` secrets, and `docs/runbooks/secret-rotation.md`.

## Pitfalls

- Agent identity lives in `data/agent-id/`; tests and scripts that recreate containers without that volume create new agent IDs (clear old ones with **Clear Offline**).
- Interface-down alerts skip virtual interfaces by name prefix (`_VIRTUAL_IFACE_PREFIXES` in `alert_evaluator.py`); add new prefixes there.
- DuckDB has one writer (manager, global lock). Opening it read-write anywhere else corrupts the design; backend access is read-only.
- Dependabot proposes one-sided `duckdb` bumps; close or combine them.
- Frontend changes do not appear in the Docker stack until the frontend image is rebuilt.
- Do not weaken CI gates (`--max-warnings=0`, `--audit-level=high`, gitleaks) to make a change pass; fix the cause.

## Done means

All CI jobs pass (or their local equivalents), migrations apply cleanly on a fresh stack (`make reset && make migrate`), README/API reference and relevant docs/runbooks are updated, and commits reference the implementation-plan step when there is one.
