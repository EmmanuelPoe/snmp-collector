# Testing

CI (`.github/workflows/ci.yml`) runs on every push and pull request. All jobs must pass before merging.

| CI job | Command(s) | Run locally |
|---|---|---|
| `lint` | `ruff check .`, `ruff format --check .`, `python scripts/check_shared.py`, `mypy --config-file ../pyproject.toml .` in backend/manager/agent, Prettier check on `frontend/src` and `e2e`, ESLint `--max-warnings=0` | same commands (ruff 0.15.22, mypy 2.3.0 pinned in CI) |
| `secret-scan` | `gitleaks git --redact` on full history | `gitleaks git --redact --verbose` |
| `dependency-audit` | `pip-audit -r {backend,manager,agent}/requirements.txt`, `npm audit --omit=dev --audit-level=high` | same |
| `backend-tests` | `cd backend && python -m pytest -q` | works without containers: `conftest.py` uses SQLite |
| `agent-tests` | `cd agent && python -m pytest -q` | same |
| `frontend-tests` | `npm run test:ci --prefix frontend` (Jest + coverage) | same, or `npm test` for watch mode |
| `manager-tests` | `docker compose run --rm --no-deps -T -e REGISTRY_BACKEND=file manager python -m pytest -q` | `make test` (manager tests are authoritative in-container) |
| `build-images` | `docker compose build` | `make build` |
| `e2e-simulation` | `make up`, Playwright `npm test --prefix e2e` (`e2e/smoke.spec.js`), then `make simulation` | needs Docker; `make simulation` + `make clean-simulation` |

The backend image has no pytest, so run backend tests on the host (`pip install -r backend/requirements.txt pytest`; Python 3.11 like CI). A local run on current `main` gave 227 passed in about 80 s. If agent tests fail with `ModuleNotFoundError: _cffi_backend`, the virtualenv is missing `cffi` for `cryptography`; reinstall the requirements in a fresh venv.

## Suites at a glance

- **backend/tests/** (~30 modules): routers (devices, alerts, agents, config, fleet, internal, metrics, topology, prometheus, maintenance, notifications, audit), auth and token lifecycle, session/password policy, rate limits, CORS, crypto, secret validation and file secrets, startup failures, structured logging, alert evaluator, trap correlation, topology suppression.
- **manager/tests/**: registration and ingest (SHA-256, dedup, DuckDB writes).
- **agent/tests/**: polling, upload buffer/retry queue, trap receiver.
- **frontend** `*.test.js`: components (Dashboard, DeviceManagement, DeviceMetrics, Sidebar, CommandPalette, HealthBar, SessionMonitor), pages (Login, ChangePassword), hooks, `services/api`, utils, theme.
- **e2e/**: Playwright smoke test against the running stack.
- **Load**: `make loadtest` (see `docs/scale-benchmark.md`); not part of CI.

## Expectations for changes

- Backend: a test for every new route covering auth (401 without a token, 403 for insufficient role) and the happy path; migrations exercised by the startup path.
- Credentials: assert they never appear in responses for viewers or in list endpoints.
- Frontend: a `*.test.js` next to new components; mock `services/api`.
- `shared/` changes: run `python scripts/sync_shared.py` so `check_shared.py` passes.
- Dependency bumps: `duckdb` changes in both backend and manager, in one PR.

## Known CI environment notes

- `e2e-simulation` is pinned to `ubuntu-24.04` because Playwright's Chromium installer does not support `ubuntu-latest` (26.04) yet; revisit when `@playwright/test` is upgraded.
