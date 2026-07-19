# Implementation Plan — Enterprise Readiness

*The detailed build sequence for the [enterprise-readiness-roadmap.md](enterprise-readiness-roadmap.md). The roadmap is the prioritized tracker (why / priority / progress); this document is the how — each step states what to change, where, the schema/migration impact, how to verify, and any decision that must be resolved before coding it. Verified against the codebase 2026-07-09 (branch `security/tier1-secret-hardening`, HEAD `500b860`). Every step carries its roadmap step number.*

## Sequencing principle

Ordered by dependency → risk → payoff. Every step is independently shippable and independently verifiable. Phase 4 (security) and the first two steps of Phase 5 (CI, lint) are the highest-value block and should land first — CI protects everything after it.

## Conventions for every step

- **Migrations**: all Postgres schema changes go through Alembic (`make migrate`). New revisions numbered after `021_encrypt_device_credentials.py`.
- **Tests**: backend tests run locally (`cd backend && python -m pytest -q` — the backend image has no pytest); manager tests are authoritative in-container (`docker-compose build manager && docker-compose run --rm --no-deps -T manager python -m pytest -q`); agent tests run locally (`cd agent && python -m pytest -q`).
- **Frontend**: source changes require `docker-compose build frontend && docker-compose up -d frontend` (Nginx serves a pre-built bundle; `npm start` hot-reload is dev-only).
- **Commits**: one logical step per commit.
- **Ownership boundaries hold**: backend owns Postgres schema; manager owns DuckDB read-write (backend mounts it read-only — never write DuckDB from the backend).

---

# Completed foundation (Phases 0–3) ✅

Feature work completed 2026-06-08 → 2026-06-30, plus the first two security steps. Summary only — full history in git.

- **Phase 0 — Bug fixes** (commits `6664ec7`, `05eefbf`): virtual-interface denylist for `interface_down`; error-rate alerting (errors/sec); OID whitelist wired end-to-end (backend `CollectionConfig` → manager → agent), `ifDescr` pinned as always-walked.
- **Phase 1 — Alerting workflow** (commits `5b96fec`…`df81209`; migrations 014–018): alert severity tiers; Slack + generic-webhook notifications (fire-and-forget, 3s timeout); maintenance windows (dedicated Maintenance page, suppress-new-only); acknowledge/assign/note workflow (`assigned_to` FK to `users.id`). Also fixed the latent speed-OID gap (migration 014) so `bandwidth_threshold` alerts can fire.
- **Phase 2 — Integration & retention** (commits `41e7e6f`, `45c3a89`, `222c02f`): Prometheus device exporter (`GET /api/metrics/prometheus`, dedicated `PROMETHEUS_SCRAPE_TOKEN`); manager weekly retention loop (`METRICS_RETENTION_DAYS`, default 90, delete-only); CSV export (per-interface max/avg). *Known flag: the exporter makes N sequential manager calls per scrape — batch it when device counts grow (picked up by Step 29/30).*
- **Phase 3 — Differentiators** (commits `9d9880b`, `863d620`, `057887e`/migration 020, `9c7f5bd`; migration 019): dynamic p95 baselines (`BASELINE_ANOMALY_ENABLED`, default off); MIB browser built on a reusable **agent command channel** (agent polls manager for commands, posts results); LLDP topology map + dependency suppression (`TOPOLOGY_SUPPRESSION_ENABLED`, default off); trap correlation into `interface_down` alerts.
- **Security Steps 1.1–1.2** (commit `500b860`; migration 021): Fernet-encrypted SNMP credentials at rest (`backend/crypto.py` `EncryptedString`); startup secret validation (`check_required_secrets()` in backend + manager), random one-time bootstrap admin password, `make up` generates strong secrets.

**Live-verification caveats carried forward:** the net-snmp simulator exposes no LLDP data and emits no traps, so topology edge-building and trap correlation are covered by synthetic unit tests only — test against real hardware before relying on them in production.

**Test baseline:** backend 156 passed · manager 80 passed · agent 3 passed. Latest migration: `021`.

---

# Phase 4 — Security hardening (roadmap Tier 1 remainder)

## Step 15 — Rate limiting + login lockout *(roadmap 1.3)* ✅ DONE (2026-07-09)

**Resolved decisions:** thresholds = the recommended defaults, all configurable
(`LOGIN_RATE_LIMIT=10/minute`, `WALK_RATE_LIMIT=6/minute`,
`LOGIN_LOCKOUT_THRESHOLD=10`, `LOGIN_LOCKOUT_MINUTES=15`, `RATE_LIMIT_ENABLED`).
Lockout status code = `423` + `Retry-After` (distinct from the limiter's `429` so
the frontend can message each case). Walk/change-password keyed per hashed session
token, not per user id.

**Built:** `backend/rate_limit.py` (limiter + `client_ip`/`token_or_ip` key funcs);
migration 022 (`failed_login_count`, `locked_until` on `users`); lockout checked
before password verification in the login route (no signal leak, counter frozen
while locked); success resets the counter; frontend `LoginPage` shows distinct
locked/rate-limited errors. 8 tests in `backend/tests/test_rate_limit.py` (suite
156 → 164); conftest disables the limiter globally so unrelated tests are
unaffected. Verified live: 429 after 11 rapid bad logins via nginx (two uvicorn
workers ⇒ limiter state is per-worker; the DB lockout is authoritative), 423 on
the locked account from a different IP.

<details><summary>Original spec</summary>

## Step 15 (original spec) — Rate limiting + login lockout *(roadmap 1.3)*

**Problem (verified):** no rate limiting anywhere — no limiter dependency in [backend/requirements.txt](../backend/requirements.txt), no `limit_req` in [nginx/conf.d/default.conf](../nginx/conf.d/default.conf). `/auth/login` is brute-forceable; `POST /devices/{id}/walk` lets an authenticated user hammer devices.

**Change:**
1. **Per-IP limits** — add `slowapi` (pinned) to the backend; wire a `Limiter` keyed by client IP into [backend/main.py](../backend/main.py). nginx already forwards `X-Real-IP`/`X-Forwarded-For` ([default.conf:24-25](../nginx/conf.d/default.conf#L24-L25)) — key on that, not the socket peer. Apply to `/auth/login` (e.g. 10/min/IP), `/auth/change-password`, and `/devices/{id}/walk` (e.g. 6/min/user).
2. **Per-account lockout** — add `failed_login_count` + `locked_until` columns to `User` ([backend/models.py:54](../backend/models.py#L54)). In the login route: increment on bad password, reset on success, set `locked_until` (e.g. 15 min) after N failures (e.g. 10). A locked account rejects even a correct password with `423`/`429` until expiry. Persisted (not in-memory) so it survives restarts and feeds the audit trail (Step 17).
3. Frontend: surface "account temporarily locked" distinctly from "wrong password".

**Migration:** `022` — add `failed_login_count`, `locked_until` to `users`.

**Verify:** backend tests — N rapid bad logins → `429`; N bad passwords → lockout rejects correct password until `locked_until`; success resets the counter. Manual: `for i in $(seq 20); do curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/auth/login …; done`.

**Decision required:** thresholds (per-IP rate, failure count, lockout duration) — recommend 10/min/IP, 10 failures → 15 min lockout, all configurable via `config.py` env settings.

</details>

## Step 16 — Token lifecycle: revocation + logout *(roadmap 1.4)* ✅ DONE (2026-07-09)

**Resolved decisions:** as specced (`token_version` + `jti` denylist, no refresh
tokens). Two design details settled during build: change-password returns a
**fresh token** (200 + `TokenResponse`, previously 204) so the current session
survives its own version bump while all other sessions die; and pre-feature
tokens (no `ver` claim) are treated as version 0, so the upgrade doesn't force a
mass re-login — the first password change does. Deactivation needed no work:
`_resolve_user` already filters `is_active`, so it was already immediate.

**Built:** migration 023 (`users.token_version`, `revoked_tokens`); `jti` claim
in every token; stale-version + denylist checks in `_resolve_user`;
`POST /auth/logout` (validly-signed token suffices — works mid
forced-password-change) with opportunistic pruning of expired denylist rows;
frontend revokes server-side on sign-out (fire-and-forget) and adopts the fresh
token after password change. 7 tests in `backend/tests/test_token_lifecycle.py`
(suite 164 → 171); verified live: logout → 401, password change → both old
sessions 401 / fresh token 200.

**Original problem (verified):** [`create_access_token`](../backend/auth.py#L27-L29) issues stateless 8h JWTs with no `jti`; [`_resolve_user`](../backend/auth.py#L32-L48) checks only signature/expiry/`is_active`. No logout endpoint exists; password change and deactivation leave old tokens valid for up to 8h.

**Change:**
1. **`token_version`** — new int column on `User`, embedded as `ver` claim in every token; `_resolve_user` rejects mismatches. Bump on password change ([backend/routers/auth.py](../backend/routers/auth.py)) and on user deactivation — invalidates all outstanding tokens for that user at once.
2. **`jti` denylist** — add a `jti` (uuid4) claim; new `revoked_tokens` table (`jti` PK, `expires_at`). `POST /auth/logout` inserts the presented token's `jti`; `_resolve_user` rejects denylisted `jti`s. Prune rows past `expires_at` opportunistically (on insert) — no new background task needed.
3. Frontend: call `/auth/logout` on sign-out instead of only dropping the token.

**Migration:** `023` — `token_version` on `users` (server_default `0`) + `revoked_tokens` table.

**Verify:** backend tests — token rejected after logout; rejected after password change; rejected after `is_active=False`; other users' tokens unaffected. The denylist check must add ≤1 indexed query per request.

**Decision required:** none — full refresh-token rotation is deliberately out of scope for v1 (8h access + version/denylist meets the revocation requirement with far less surface). Revisit only if idle-session policy (Step 38) forces shorter access tokens.

## Step 17 — Audit logging *(roadmap 1.5)* ✅ DONE (2026-07-15)

**Built:** as specced — `audit_log` table (migration `024`), `backend/audit.py`
`record()` helper (X-Real-IP source, credential redaction incl. webhook `url`),
hooks in every mutating router, admin-only paginated/filterable `GET /audit`
(`backend/routers/audit_log.py`), frontend admin Audit Log page, and
`AUDIT_RETENTION_DAYS=400` weekly prune task in the backend lifespan.
18 tests in `backend/tests/test_audit.py`; suite now 189. Deploy: `make migrate`.

**Problem (verified):** no audit trail — `grep -ri audit backend/` returns nothing. Logins, device/credential changes, config edits, and alert actions leave no "who/what/when" record. Prerequisite for the compliance pack (Step 41).

**Change:**
1. **Model + migration** — `audit_log` table: `id`, `actor_user_id` (nullable FK — null for failed logins), `actor_email`, `action` (e.g. `device.create`, `auth.login_failed`), `target_type`, `target_id`, `summary` (JSON — changed fields only, **credential values redacted**), `source_ip`, `created_at`. Append-only: no update/delete route exists for it.
2. **Helper** — new `backend/audit.py`: `record(db, request, actor, action, target_type=…, target_id=…, summary=…)` — reads `X-Real-IP` from the request, commits with the caller's transaction.
3. **Hooks** — call from every mutating router: `auth` (login success/failure, password change, logout), `devices` (CRUD + walk), `config`, `alerts` (resolve/ack/assign/note), `alert-rules`, `notifications`, `maintenance`, `topology` (discover), and user management. GET endpoints are not audited except exports (Step 40).
4. **Admin view** — `GET /audit` (admin-only, paginated, filterable by actor/action/target/date) + a frontend admin Audit page.

**Migration:** `024` — `audit_log` table + indexes on (`created_at`), (`actor_user_id`), (`target_type`, `target_id`).

**Verify:** backend tests per hooked action; failed login records the source IP with null actor; device update summary contains changed field names but never `snmp_community`/`auth_password`/`priv_password` values.

**Decision required:** audit retention length — recommend `AUDIT_RETENTION_DAYS=400` (>1 year, covers annual reviews), pruned by a weekly task mirroring the manager's `_retention_loop` pattern.

## Step 18 — CORS tightening + TLS + security headers *(roadmap 1.6)* ✅ DONE (2026-07-15)

**Built:** as specced, with the recommended decisions adopted (dev compose stays
HTTP; TLS via opt-in `docker-compose.tls.yml` overlay that Step 33's prod
profile will fold in; HSTS starts at max-age=300). CORS restricted in
`backend/main.py` (+ `tests/test_cors.py`, suite now 192); shared
`nginx/security_headers.inc` (CSP Report-Only fitted to the CRA bundle — flip
to enforcing after a quiet period); TLS vhost `nginx/conf.d-tls/default.conf`
with 80→443 redirect and `/agent/` manager route (client_max_body_size 50m for
parquet ingest); `scripts/gen_self_signed_cert.sh`; `docs/runbooks/tls.md`
(Let's Encrypt / corporate CA / self-signed + HSTS rollout). `nginx/certs/` is
gitignored. **Pending (Docker down at build time):** `nginx -t`, curl header
checks, agent-over-TLS e2e, `make simulation`.

**Problem (verified):** CORS allows all methods and headers ([backend/main.py:83-89](../backend/main.py#L83-L89)). nginx listens on plain HTTP :80 only ([nginx/conf.d/default.conf:2](../nginx/conf.d/default.conf#L2)) — no TLS, no HSTS, no security headers. Remote agents reach the manager on :8001 in cleartext carrying SNMP credentials in device-config responses.

**Change:**
1. **CORS** — restrict to `allow_methods=["GET","POST","PUT","DELETE"]`, `allow_headers=["Authorization","Content-Type"]` in [backend/main.py](../backend/main.py).
2. **nginx TLS** — add a 443 server block (`ssl_certificate` from a mounted `nginx/certs/` dir), redirect 80→443, `Strict-Transport-Security` (start `max-age=300` during rollout, raise to 6 months once stable). Keep the existing runtime-DNS-resolution pattern and the `/api/internal/` deny block.
3. **Security headers** — `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and a CSP fitted to the React bundle (start `Content-Security-Policy-Report-Only`, tighten, then enforce).
4. **Manager TLS** — route agent traffic through nginx too: new `https://…/agent/` location proxying to `manager:8001`, so one cert covers both hops; agents set `MANAGER_URL` accordingly. Direct :8001 stays for compose-internal (backend↔manager) traffic and stops being published in the prod overlay (Step 33).
5. **Cert management doc** — `docs/runbooks/tls.md`: Let's Encrypt path, corporate-CA path, and a self-signed bootstrap script for dev.

**Migration:** none.

**Verify:** `curl -I https://host` shows HSTS + security headers; `curl -I http://host` returns 301 to https; a disallowed CORS method is rejected; agent completes register→poll→ingest through the TLS endpoint; `make simulation` still passes inside the compose network.

**Decision required:** whether dev compose also runs TLS (self-signed) or stays HTTP — recommend HTTP for dev, TLS only in the prod overlay, so `make up` stays zero-config.

## Step 19 — Per-agent credentials *(roadmap 1.7)* ✅ DONE (2026-07-15)

**Built:** as specced, ahead of Step 25 (secret_hash lives on the file-based
registry record and will migrate to Postgres with it). Per-agent secret issued
once at `/register`/`/claim` (`registry.new_secret()`, SHA-256 hash stored);
`require_agent_auth` + `ensure_same_agent` in `manager/auth.py` guard
heartbeat, `GET /config/{agent_id}`, `/ingest`, command fetch/result; the
recommended grace mode landed as `AGENT_AUTH_ENFORCE=false` (shared key
accepted on agent routes with a warning — flip to true next release). Agent
persists the secret 0600 (`agent/credentials.py`) and sends
`Bearer <agent_id>:<secret>` everywhere; `MANAGER_API_KEY` optional for agents
(claim path needs none; dev compose keeps it for `/register` bootstrap only).
Tests: manager 84+10 local (6 known-spurious 401-vs-403 remain), agent 7.
**Pending (Docker down):** in-container manager suite, `make simulation`.

**Problem (verified):** one-time **enrollment** tokens already exist — [`/claim`](../manager/routers/registration.py#L19-L30) consumes a slot token from `manager/slots.py` — but every subsequent agent call (heartbeat, config, ingest, commands) authenticates with the single shared `MANAGER_API_KEY` ([manager/auth.py:11](../manager/auth.py#L11)), which is the same credential the backend accepts for internal endpoints ([backend/auth.py:81-86](../backend/auth.py#L81-L86)). A key extracted from any agent host compromises every hop and never rotates.

**Change:**
1. **Issue at claim/register** — manager generates a per-agent secret (`secrets.token_urlsafe(32)`), returns it once in the `ClaimResponse`/`RegisterResponse`, stores only a hash on the registry record (`AgentInfo` in [manager/registry.py](../manager/registry.py); the field migrates to Postgres with Step 25 — no hard ordering dependency, but landing 25 first avoids doing the schema twice).
2. **Agent side** — persist the secret alongside the agent-ID file (`data/agent-id/`, mode 0600); send `Authorization: Bearer <agent_id>:<secret>` on all calls ([agent/uploader.py:70](../agent/uploader.py#L70), heartbeat/config/command calls in [agent/main.py](../agent/main.py)).
3. **Manager side** — new `require_agent_auth` dependency (constant-time hash compare) on agent-facing routes: heartbeat, `GET /config/{agent_id}`, `/ingest`, command fetch/result. `require_api_key` (shared key) remains only on operator/backend-facing routes (`/register` bootstrap, agent list, deregister, enqueue-command). An agent may only act as itself (`agent_id` in path/payload must match the authenticated identity).
4. **Revocation** — deregister deletes the record → credential dead. Re-enrollment issues a fresh secret.
5. **Backend internal endpoints** unchanged (manager-only via `MANAGER_API_KEY`) — the win is that agent hosts no longer hold that key at all. Remove `MANAGER_API_KEY` from the agent's compose environment.

**Migration:** none (registry is file/Postgres-side, not Alembic-managed until Step 25).

**Verify:** manager tests — agent A's credential cannot heartbeat as agent B; revoked agent gets 401 on every route; shared key no longer accepted on agent routes; agent env without `MANAGER_API_KEY` completes claim→poll→ingest. `make simulation` passes.

**Decision required:** migration path for already-enrolled agents — recommend a one-release grace mode (`AGENT_AUTH_ENFORCE=false` accepts both schemes, log a warning on shared-key use), then flip the default.

---

# Phase 5 — CI & quality gates (roadmap Tier 3)

Start Steps 20–21 in parallel with Phase 4 — they protect every later change.

## Step 20 — CI pipeline *(roadmap 3.1)* ✅ DONE (2026-07-09)

**Built:** `.github/workflows/ci.yml` with the five specced jobs (backend-tests,
manager-tests in-container, agent-tests, build-images, e2e-simulation with
compose-logs artifact on failure) plus a `docker-compose` shim for runners that
only ship the `docker compose` plugin. **Latent bug found and fixed:**
`scripts/run_simulation.sh` had been broken by Step 1.2 (hardcoded
`admin@localhost / changeme`, but the bootstrap password is now random) and by
Step 1.4 (it kept using the pre-password-change token, now version-stale) — it
now parses the one-time bootstrap password from the backend log (or takes
`SIM_ADMIN_EMAIL`/`SIM_ADMIN_PASSWORD`) and adopts the fresh token returned by
change-password. Verified: workflow YAML parses; the repaired simulation script
ran green locally against the live stack including the forced-change path.
**Manual follow-up:** enable branch protection on `main` requiring the five
checks (GitHub settings — can't be done from the repo).

**Original problem (verified):** no `.github/workflows` directory exists. Nothing runs tests or builds on a PR.

**Change:** `.github/workflows/ci.yml` with jobs:
1. `backend-tests` — Python 3.x, `pip install -r backend/requirements.txt`, `cd backend && python -m pytest -q`.
2. `manager-tests` — build the manager image and run pytest **in-container** (`docker-compose build manager && docker-compose run --rm --no-deps -T manager python -m pytest -q`) — the container is authoritative (local Starlette-version skew causes spurious 401-vs-403 failures).
3. `agent-tests` — `cd agent && python -m pytest -q`.
4. `build` — `docker compose build` (all six images).
5. `e2e-simulation` — `make up` with generated secrets, `make simulation`, `make clean-simulation`; upload compose logs as an artifact on failure.
Then enable branch protection on `main` requiring all jobs.

**Migration:** none.

**Verify:** a PR with a deliberately broken test is red and unmergeable; a clean PR is green across all five jobs.

**Decision required:** none.

## Step 21 — Lint, format, type-check gates *(roadmap 3.2)* ✅ DONE (2026-07-15)

**Built:** root `pyproject.toml` (ruff lint+format: defaults + I + W, E711/E712
ignored for the SQLAlchemy idiom, E402 allowed in tests; mypy per service with
a lenient baseline — SQLAlchemy/pydantic noise codes disabled, ratchet plan
documented in the file). Frontend `.prettierrc`/`.prettierignore` + prettier
pinned as a devDependency; eslint = CRA `react-app` config at
`--max-warnings=0` (two pre-existing warnings fixed). `.pre-commit-config.yaml`
with ruff-check/ruff-format/prettier/eslint — `pre-commit run --all-files`
green. Format-only commit `b8c45ec` (131 files). CI `lint` job added to the
Step 20 workflow. Verified: injected violation fails ruff (F821) and mypy
(name-defined); all pytest suites + frontend build green post-format.

**Problem (verified):** no `pyproject.toml`, `.pre-commit-config.yaml`, `.eslintrc`, or `.prettierrc` anywhere in the repo.

**Change:**
1. Root `pyproject.toml`: `ruff` for lint **and** format (one tool, no black), `mypy` per service starting lenient (`ignore_missing_imports`, no `strict`) with a ratchet plan.
2. Frontend: `eslint` (react-app config already implied by CRA) + `prettier`, config checked in.
3. `.pre-commit-config.yaml`: ruff, ruff-format, prettier, eslint.
4. One dedicated **format-only commit** applying ruff-format/prettier across the repo (keeps review noise out of functional commits).
5. New CI job `lint` added to Step 20's workflow.

**Migration:** none.

**Verify:** CI fails on an injected lint/type violation; `pre-commit run --all-files` passes locally after the format commit.

**Decision required:** none (mypy strictness ratchets later; don't block this step on typing debt).

## Step 22 — Dependency + image scanning, SBOM *(roadmap 3.3)* ✅ DONE (2026-07-19)

**Built:** as specced — CI `dependency-audit` job (pip-audit ×3 + npm audit
prod-deps at high), Trivy on the five built images with
`--severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` + `.trivyignore`
policy file (reason + expiry required per entry), syft SPDX SBOM per image
uploaded as a build artifact, and `.github/dependabot.yml` (pip ×3, npm,
docker ×5, github-actions, weekly). Day-one findings resolved by bumping pins
(fastapi 0.109.1, cryptography 48.0.1, python-multipart 0.0.31, pyarrow 23.0.1,
jinja2 3.1.6, pytest 9.0.3 + pytest-asyncio 1.3.0, `npm audit fix`) — all
suites + frontend build validated green under the new versions locally; one
expiry-tagged allowlist entry (PYSEC-2026-2263, pyasn1/pysnmp, 2026-10-31).
**Pending:** first CI run exercises Trivy/syft + in-container tests under the
bumped pins; Dependabot activates once the branch reaches GitHub.

**Problem (verified):** all requirements are pinned (good) but nothing scans them; no SBOM; no Dependabot config.

**Change:** CI jobs: `pip-audit -r */requirements.txt`, `npm audit --audit-level=high` (frontend), Trivy scan of each built image, `syft` SBOM per image uploaded as build artifact. `.github/dependabot.yml` for pip (3 services), npm, docker, and github-actions ecosystems. Policy: fail CI on **fixable** HIGH/CRITICAL findings; unfixable ones get an allowlist entry with an expiry comment.

**Migration:** none.

**Verify:** temporarily pinning a known-vulnerable package turns CI red; SBOM artifacts appear per build; Dependabot opens PRs.

**Decision required:** none.

## Step 23 — Secret scanning *(roadmap 3.4)*

**Problem (verified):** `.env` exists in the working tree (gitignored, but one `git add -f` from disaster); no gitleaks/trufflehog anywhere.

**Change:** `gitleaks` in CI (full-history scan once, then diff scans per PR) and as a pre-commit hook; confirm `.env`, `data/`, and `nginx/certs/` are gitignored; if the history scan finds real secrets, rotate them (the Step 1.2 machinery makes rotation cheap) rather than rewriting history.

**Migration:** none.

**Verify:** a PR introducing an AWS-key-shaped string is blocked; history scan report is clean or all findings rotated.

**Decision required:** none.

## Step 24 — Frontend + E2E test coverage *(roadmap 3.5)*

**Problem (verified):** zero test files under `frontend/src`; `frontend/package.json` has CRA's default `react-scripts test` but no testing-library deps; the only E2E is the manual `make simulation`.

**Change:**
1. Add `@testing-library/react` + `@testing-library/user-event`; component tests for the three critical flows: login (success, failure, forced password change), device CRUD modal (create/edit incl. alert thresholds), alert feed (render, ack, resolve). Mock `fetch` at the API boundary.
2. Playwright happy-path E2E in CI, running against the compose stack from Step 20's e2e job: login → add device (simulator IP) → wait for metrics → see chart → alert feed loads.
3. CI reports frontend coverage with a floor (start where it lands, ratchet up; never down).

**Migration:** none.

**Verify:** `npm test -- --watchAll=false` green; Playwright passes headless in CI; coverage report visible per PR.

**Decision required:** none.

---

# Phase 6 — Reliability & 1000-device scale (roadmap Tier 2)

## Step 25 — Agent registry into Postgres *(roadmap 2.1)*

**Problem (verified):** the manager keeps the registry in memory and persists to a JSON file ([manager/registry.py:81-86](../manager/registry.py#L81-L86)). The write is already atomic (tmp + `os.replace`), but state is lost on volume loss, invisible to backups, not queryable, and a corrupt file is silently discarded ([registry.py:96-97](../manager/registry.py#L96-L97)). Per-agent credential hashes (Step 19) need a durable home.

**Change:**
1. **Schema owned by backend Alembic** (single migration authority), **data owned by manager read-write** — a documented exception mirroring the DuckDB arrangement in reverse. New `agent_registry` table: `agent_id` PK, `hostname`, `ip`, `last_seen`, `pending_uploads`, `credential_hash`, `created_at`.
2. **Manager** gains a minimal Postgres connection (async `psycopg`/SQLAlchemy Core — no ORM needed): `Registry` keeps its in-memory dict as a cache, `_persist()` becomes an upsert, `_load()` a `SELECT` at startup. Connection settings via `DATABASE_URL` in [manager/config.py](../manager/config.py) + compose.
3. Keep the JSON file path as a **dev fallback** (`REGISTRY_BACKEND=file|postgres`, default `postgres` in compose) so unit tests need no DB.
4. Transient enrollment slots (`manager/slots.py`) stay in-memory — they are TTL'd one-time tokens; losing them on restart is correct behavior.

**Migration:** `025` — `agent_registry` table.

**Verify:** manager tests for the Postgres backend (upsert, load, deregister); wiping the manager container/volume preserves registrations; `pg_dump` includes registry rows; heartbeat load (100 agents × 30s) shows no measurable overhead.

**Decision required:** none — the schema-in-Alembic/data-in-manager split is the recommendation; the alternative (manager proxies through backend HTTP) adds a hop and couples manager liveness to backend, rejected.

## Step 26 — Harden silent failure paths *(roadmap 2.2)*

**Problem (verified):** four swallow-alls:
- [manager/db.py:44-45](../manager/db.py#L44-L45) — `except Exception: pass` around DuckDB schema migration.
- [backend/main.py:63-64](../backend/main.py#L63-L64) — bootstrap swallows `OperationalError`, so the backend starts "healthy" with a dead Postgres.
- [manager/registry.py:96-97](../manager/registry.py#L96-L97) — corrupt registry JSON silently discarded (moot after Step 25 for prod, still live for the file fallback).
- [agent/uploader.py:78-79](../agent/uploader.py#L78-L79) — every upload failure (auth error, 4xx, network) is silently dropped into the retry queue with no log line.

**Change:** narrow each to the specific expected exception; log WARNING/ERROR with context. Backend bootstrap: let `OperationalError` propagate — a dead DB should fail startup, not defer to the first request. DuckDB `_migrate`: catch only the "table does not exist" case, log and re-raise anything else. Uploader: log the failure (status code / exception) at WARNING before queueing; a 4xx that will never succeed (401/413) should log ERROR so operators see auth/config breakage rather than a silently growing queue.

**Migration:** none.

**Verify:** unit tests injecting each failure assert a log record (caplog) and correct behavior — backend startup aborts without Postgres (compose healthcheck + restart policy handles retry-on-boot ordering); corrupt registry file logs and quarantines (rename `.corrupt`) instead of vanishing.

**Decision required:** none.

## Step 27 — Liveness/readiness + ingest backpressure *(roadmap 2.3)*

**Problem (verified):** both services expose a static [`/health`](../backend/main.py#L112-L114) that checks nothing; compose healthchecks exist only for postgres, backend, and manager; frontend/nginx/agent have none. No backpressure: `/ingest` waits on the global DuckDB write lock ([manager/db.py:8](../manager/db.py#L8)) unboundedly.

**Change:**
1. **Backend** — `/health/live` (static) and `/health/ready` (Postgres `SELECT 1` + DuckDB read probe). Keep `/health` as an alias for live (nginx location already proxies it).
2. **Manager** — `/health/live` and `/health/ready` (DuckDB writable probe + registry backend reachable).
3. **Compose healthchecks** for every service: frontend (`wget -qO- localhost` — it's an nginx static server), nginx (`curl -f localhost/health`), agent (no HTTP server — `CMD` checks a heartbeat file the main loop touches each cycle), simulator (udp probe or process check). Point existing backend/manager checks at `/health/ready`.
4. **Backpressure** — track write-lock waiters in [manager/db.py](../manager/db.py) (counter around `_write_lock`); when waiters > threshold (config `INGEST_MAX_QUEUE`, e.g. 8), `/ingest` returns `503` + `Retry-After: 30` **before** reading the upload body. The agent needs no change to survive it — a non-2xx leaves the Parquet file in the disk queue for `_retry_loop` ([agent/uploader.py:61-79](../agent/uploader.py#L61-L79)) — but with Step 26's logging it should log 503 at INFO (expected deferral), not WARNING.

**Migration:** none.

**Verify:** stop Postgres → backend `/health/ready` 503 while `/health/live` 200; `docker ps` shows health for all services; a load test holding the write lock makes `/ingest` return 503 and the agent's queue drains afterward with no data loss (row counts match).

**Decision required:** none.

## Step 28 — Backups + tested restore *(roadmap 2.4)*

**Problem (verified):** no backup tooling exists — `scripts/` holds only `run_simulation.sh`; no Makefile backup target; neither Postgres (`postgres_data` volume) nor the DuckDB file (`data/db/metrics.db`) is protected.

**Change:**
1. **Postgres** — `scripts/backup.sh`: `pg_dump -Fc` via `docker-compose exec -T postgres`, timestamped into `BACKUP_DIR`, retention of last N.
2. **DuckDB** — a copy of a live single-file DB is unsafe while the writer holds it. Add manager `POST /internal/backup` (shared-key auth): inside `_write_lock`, `CHECKPOINT`, copy the file to the backup dir, release. Serialized with ingest by construction; ingest deferrals during the copy are absorbed by Step 27 backpressure.
3. **Registry** rides the Postgres dump (Step 25).
4. `make backup` / `make restore BACKUP=<timestamp>` targets; scheduling documented for host cron (single-host posture — no scheduler container needed).
5. **Runbook** — `docs/runbooks/restore.md`: full-host restore drill, stated **RPO = backup interval (default 24h)**, **RTO target ≤ 30 min**.

**Migration:** none.

**Verify:** `make backup` produces both artifacts while ingest is running (row counts consistent after); restore drill on a clean checkout reconstructs users, devices, alerts, registry, and metrics; a metric collected after the backup is absent post-restore (proves the restore actually swapped the data).

**Decision required:** default backup schedule/retention — recommend daily, keep 14; both configurable.

## Step 29 — Load-test harness at 1000 devices *(roadmap 2.5)*

**Problem (verified):** the 1000-device target is unproven. Expected pressure points: the single write lock ([manager/db.py:8](../manager/db.py#L8)); the evaluator's per-device rates fetches every 30s ([backend/alert_evaluator.py](../backend/alert_evaluator.py)); the Prometheus exporter's N-sequential-manager-calls-per-scrape (flagged in Phase 2); DuckDB query latency as `snmp_polls` grows to ~10⁹ rows/90d at target load (1000 devices × ~30 interfaces × ~10 OIDs / 60s poll ≈ 5k rows/s).

**Change:**
1. **Synthetic ingest generator** (`scripts/loadtest/ingest_load.py`) — bypasses SNMP: generates realistic Parquet batches for N synthetic devices and uploads them through the real `/ingest` path at a configurable rate. This isolates the manager/DuckDB ceiling, which is the actual question.
2. **Query load driver** — concurrent calls against the backend's metrics/rates endpoints and one Prometheus-exporter scrape, mimicking a dashboard-open fleet.
3. **Evaluator timing** — log/emit `run_evaluation` duration (it must fit inside its 30s cadence at 1000 devices).
4. **Metrics captured:** sustained ingest rows/s, `/ingest` p50/p99, write-lock wait p99, backend query p99, exporter scrape duration, evaluator loop duration, DuckDB file growth rate, container CPU/RSS (feeds Step 32 limits).
5. **Deliverables:** `make loadtest` + `docs/scale-benchmark.md` with the numbers and the test recipe.

**Migration:** none.

**Verify:** `make loadtest` runs against a fresh stack and emits the report; results are reproducible within ~10% across two runs.

**Decision required:** none — this step produces the data; Step 30 makes the call.

## Step 30 — Metrics-store decision gate *(roadmap 2.6)*

**Problem:** whether DuckDB survives the target is empirical. Decide from Step 29's numbers against criteria fixed **before** the run.

**Pass criteria (at 1000-device simulated load, sustained 1h):** ingest keeps up with zero agent-queue growth; `/ingest` p99 < 2s; backend query p99 < 2s with query load applied; evaluator loop < 15s; exporter scrape < 30s (Prometheus default timeout).

**Branch (a) — pass → keep DuckDB and tune:** batch/coalesce ingest writes; date-partition or index `snmp_polls`; batch the exporter's per-device calls into one manager endpoint; document the measured ceiling and the headroom.

**Branch (b) — fail → hot path to TimescaleDB:** TimescaleDB is already in the stack. Manager dual-writes (or writes Timescale-only) `snmp_polls` as a hypertable; backend metrics/rates queries move to Postgres (killing the read-only DuckDB mount and its coupling); DuckDB retained only for columnar batch/export if still useful. This is a large step — if chosen, it gets specced as its own numbered step before coding.

**Migration:** none for (a); (b) brings hypertable migrations + compression/retention policies.

**Verify:** re-run `make loadtest` after the chosen branch; publish before/after in `docs/scale-benchmark.md`; the pass criteria hold.

**Decision required:** the branch itself — made by the numbers, not in advance. Do not pre-build (b).

---

# Phase 7 — Production operations (roadmap Tier 4)

## Step 31 — Non-root containers, least privilege *(roadmap 4.1)*

**Problem (verified):** only [manager/Dockerfile](../manager/Dockerfile) creates and switches to a non-root user; backend, agent, and frontend run as root. No `cap_drop`, no read-only rootfs.

**Change:**
1. Backend + agent Dockerfiles: replicate the manager's `addgroup`/`adduser`/`USER app` pattern; `chown` the writable paths (agent: `data/agent-id/`, `data/agent-queue/`).
2. Frontend: switch base to `nginxinc/nginx-unprivileged` (listens 8080) or configure non-root temp/pid paths; adjust the compose port mapping.
3. Traps: default `TRAP_LISTEN_PORT` stays 162 in docs but the prod overlay maps host 162 → container high port (e.g. 1162) so no capability is needed; document `cap_add: NET_BIND_SERVICE` as the alternative.
4. Prod overlay (Step 33): `cap_drop: [ALL]` + selective `cap_add`, `read_only: true` + `tmpfs` where feasible (backend/manager write only their data mounts).

**Migration:** none.

**Verify:** `docker-compose exec <svc> id` → non-root UID for all six; `make simulation` passes; traps still received on the mapped port.

**Decision required:** none.

## Step 32 — Resource limits *(roadmap 4.2)*

**Problem (verified):** no `cpus`/`mem_limit`/`deploy.resources` anywhere in [docker-compose.yml](../docker-compose.yml).

**Change:** per-service CPU/memory limits in the prod overlay (Step 33), sized from Step 29's measured RSS/CPU at target load + ~50% headroom; document each number and its source in the overlay comments. Dev compose stays unlimited.

**Migration:** none.

**Verify:** stack runs the load test within limits (no OOM kills — check `docker events`); a deliberately tiny limit on a test service demonstrates containment.

**Decision required:** none (numbers come from Step 29; sequence this after it).

## Step 33 — Production compose profile + runbooks *(roadmap 4.3)*

**Problem (verified):** one compose file serves dev and prod; postgres publishes 5432 and manager 8001 to the host; no restart policies; no log rotation; no install/upgrade procedure. (Replaces the earlier Helm/K8s idea per the locked single-host decision.)

**Change:**
1. `docker-compose.prod.yml` overlay: TLS nginx (Step 18), `restart: unless-stopped` everywhere, `logging` driver opts (`max-size: 50m`, `max-file: 5`), **no published ports** except nginx 80/443 (and the trap UDP port), pinned image tags (`:v1.x`, not `latest`), resource limits (Step 32), hardening flags (Step 31).
2. Image versioning: tag images with the release version in CI; compose prod references tags.
3. Runbooks under `docs/runbooks/`: `install.md` (clean host → healthy stack, secrets bootstrap, TLS), `upgrade.md` (pull, migrate, restart order, verify), `rollback.md` (previous tag + restore from Step 28 if migrations are irreversible).
4. README gains a "Production deployment" section pointing at the overlay + runbooks.

**Migration:** none.

**Verify:** a clean VM reaches a healthy, TLS-serving stack following `install.md` verbatim; `docker ps` on prod shows no unexpected published ports; upgrade + rollback drill succeeds.

**Decision required:** none.

## Step 34 — Single-host secrets handling *(roadmap 4.4)*

**Problem (verified):** all secrets (`JWT_SECRET`, `MANAGER_API_KEY`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`) live in a flat `.env` consumed as environment variables; environment is visible via `docker inspect` to anyone with docker-socket access; rotation is undocumented.

**Change:**
1. Compose `secrets:` (file-based) in the prod overlay for the four secrets; files root-owned `0600` under `/etc/snmp-collector/secrets/`.
2. Config support: backend/manager/agent `config.py` read `<NAME>_FILE` when set, falling back to the env var (dev keeps `.env` — `make up` generation unchanged).
3. `check_required_secrets()` (Step 1.2) validates whichever source supplied the value.
4. `docs/runbooks/secret-rotation.md` per secret: `MANAGER_API_KEY` (restart order: backend+manager together, then agents re-enroll if Step 19's grace mode is off), `JWT_SECRET` (all sessions invalidated — announce), `ENCRYPTION_KEY` (requires a re-encryption migration path — document as "supported via rotate-and-migrate script", build the script here), `POSTGRES_PASSWORD`.
5. Vault/KMS integration explicitly out of scope for single-host (recorded in the roadmap scope table).

**Migration:** none (the `ENCRYPTION_KEY` rotation script is a standalone management command, not an Alembic revision).

**Verify:** prod stack boots with zero secrets in `docker inspect` env output; each rotation procedure executed on a test stack without data loss (encrypted credentials still decrypt after key rotation).

**Decision required:** none.

---

# Phase 8 — Observability & SRE (roadmap Tier 5)

## Step 35 — Shared structured logging + correlation IDs *(roadmap 5.1)*

**Problem (verified):** JSON logging is ad-hoc `json.dumps` duplicated across seven modules ([backend/main.py](../backend/main.py), `manager/main.py`, `manager/slots.py`, `manager/registry.py`, `manager/services/ingest.py`, `agent/main.py`, `agent/trap_receiver.py`) with no shared schema and no request correlation across backend→manager→agent.

**Change:**
1. **Shared module** — single-file `shared/logging_json.py` (formatter + `get_logger` + correlation-ID contextvar), copied into each image at build (`COPY shared/ …` — requires widening each service's compose build context to the repo root, or a small `cp` in each Dockerfile build stage). A CI check (Step 20 lint job) asserts the three copies are identical if vendored instead.
2. **Schema:** `ts`, `level`, `service`, `logger`, `msg`, `correlation_id`, plus contextual extras (`agent_id`, `device_ip`, `file_id`).
3. **Propagation:** FastAPI middleware (backend + manager) reads/generates `X-Correlation-ID` into the contextvar and echoes it in responses; all `httpx` calls (backend↔manager, manager→backend, agent→manager) forward it; the agent stamps a fresh ID per upload/poll cycle so one upload is traceable end-to-end.
4. Replace the seven ad-hoc call sites.

**Migration:** none.

**Verify:** `make simulation`, then grep one upload's correlation ID across backend, manager, and agent logs — full path visible; all services' log lines parse against the same schema (a small test asserts required fields).

**Decision required:** build-context widening vs vendored copies — recommend widening the build context (one source of truth); it costs a slightly larger build context only.

## Step 36 — Observability overlay: dashboards + alert rules as code *(roadmap 5.2)*

**Problem (verified):** `docker-compose.observability.yml` is referenced by `.env.example` (with `GF_SECURITY_ADMIN_PASSWORD`) **but does not exist**; `observability/` contains only an empty `loki/` dir; no Grafana dashboards or platform alert rules are checked in. Prometheus HTTP metrics are already exposed (`/internal/prometheus` via Instrumentator, [backend/main.py:91](../backend/main.py#L91)).

**Change:**
1. **Create `docker-compose.observability.yml`**: Prometheus (scrapes backend + manager `/internal/prometheus` and the device exporter with `PROMETHEUS_SCRAPE_TOKEN`), Grafana (provisioned datasources + dashboards from `observability/grafana/`), Loki + Promtail (container logs — the Step 35 JSON schema makes them queryable by field).
2. **Platform metrics to add** (backend/manager instrumentation): ingest rows/s + `/ingest` latency histogram, write-lock wait, agent-queue depth (from heartbeat `pending_uploads`), evaluator loop duration, DuckDB file size.
3. **Dashboards as code:** platform health (ingest freshness, queue depth, agent status, evaluator duration, DB sizes) + device overview.
4. **Prometheus alert rules as code** (`observability/prometheus/alerts.yml`): ingest freshness stalled, agent offline, evaluator overrun, disk >80%, backup age > RPO (Step 28).
5. Reconcile the stray `prometheus/` dir (snmp_exporter config) — move under `observability/` or document its separate purpose; ensure every file `.env.example`/README references exists.

**Migration:** none.

**Verify:** `docker-compose -f docker-compose.yml -f docker-compose.observability.yml up` → Grafana auto-provisioned with working dashboards; stopping the agent fires the ingest-freshness alert; Loki query by `correlation_id` returns cross-service lines.

**Decision required:** none.

## Step 37 — SLO definitions (+ optional OTel) *(roadmap 5.3)*

**Problem:** no SLOs — "healthy enough?" has no defined answer; error budgets can't burn.

**Change:** `docs/slo.md` defining, with Prometheus recording rules + Grafana budget panels: ingest freshness (99% of devices' newest metric ≤ 2 poll intervals old), API availability/latency (99.9% non-5xx, p99 < 500ms), evaluator timeliness (99% of loops < 15s). OpenTelemetry tracing: **deferred** — correlation IDs (Step 35) cover the debugging need at this scale; record the reopen trigger (multi-hop latency mysteries the logs can't resolve).

**Migration:** none.

**Verify:** recording rules evaluate; a simulated ingest stall visibly burns the freshness budget on the dashboard.

**Decision required:** the SLO targets themselves — the numbers above are recommendations; confirm before publishing them as commitments.

---

# Phase 9 — Compliance & governance (roadmap Tier 6)

## Step 38 — Password + session policy *(roadmap 6.1)*

**Problem (verified):** password policy is `min_length=8` only ([backend/routers/auth.py:27](../backend/routers/auth.py#L27)); no complexity/common-password check; no idle-session timeout (tokens live a flat 8h regardless of activity).

**Change:**
1. `backend/password_policy.py`: configurable min length (default 12), require character classes (configurable), reject a bundled common-password list (e.g. top-10k) and the user's own email local-part. Enforce on change-password and admin user-creation.
2. Idle timeout: shorten access-token lifetime (e.g. `JWT_EXPIRE_HOURS` default 8 → configurable 1) + frontend silent re-issue on activity via a `/auth/refresh` endpoint gated by the Step 16 version/denylist checks; absolute session cap (e.g. 12h) via an `iat`-based check.
3. Frontend: auto-logout on 401, idle-warning toast.

**Migration:** none (policy is config; lockout columns landed in Step 15).

**Verify:** weak/common passwords rejected with actionable messages; an idle session expires at the configured timeout while an active one persists to the absolute cap.

**Decision required:** policy defaults (min length, classes, idle + absolute timeouts) — recommend 12 chars / no forced classes but common-password rejection / 60 min idle / 12h absolute; all configurable.

## Step 39 — RBAC gating audit + pagination caps *(roadmap 6.2)*

**Problem (verified):** three roles exist (`admin`/`editor`/`viewer`, [backend/models.py:48-51](../backend/models.py#L48-L51)) with `require_role` gating ([backend/auth.py:72-78](../backend/auth.py#L72-L78)), but no documented route→role matrix verifies every mutating route is gated as intended. `GET /alerts` returns **all rows unpaginated** ([backend/routers/alerts.py:19-28](../backend/routers/alerts.py#L19-L28)); `GET /devices` accepts `limit` with no ceiling ([backend/routers/devices.py:54](../backend/routers/devices.py#L54)).

**Change:**
1. **Matrix** — `docs/rbac-matrix.md`: every route × role, generated by inspecting router dependencies; a test walks all app routes asserting each mutating route carries `require_role` (catches future unguarded routes structurally, not per-route).
2. **Pagination** — `limit: int = Query(100, le=500)` pattern on every list endpoint; add `skip`/`limit` to `/alerts` (+ total-count header or existing `/alerts/count` for the frontend badge); audit `config`, `agents`, `maintenance`, `notifications`, audit-log routers for the same.
3. Frontend: alert feed pages or infinite-scrolls instead of assuming the full list.

**Migration:** none.

**Verify:** the structural RBAC test passes (and fails when a test route is added ungated); `GET /alerts?limit=10000` returns ≤500; viewer/editor permission tests per the matrix.

**Decision required:** none.

## Step 40 — Audited data export *(roadmap 6.3)*

**Problem (verified):** metrics CSV export exists (Phase 2, `GET /api/metrics/export/csv/{device_id}`), but alerts and audit logs have no export, and no export leaves an audit trace.

**Change:**
1. `GET /alerts/export/csv` (filterable: status/severity/date range) and `GET /audit/export/csv` (admin-only, filterable) following the existing CSV streaming pattern from the metrics export.
2. Every export endpoint (including the existing metrics CSV) records an audit row (Step 17 helper) with the filter parameters in the summary.
3. Frontend export buttons on the alert feed and audit page.

**Migration:** none.

**Verify:** exports produce complete artifacts matching the applied filters; each export creates exactly one audit row naming the actor and parameters.

**Decision required:** none.

## Step 41 — Compliance evidence pack *(roadmap 6.4)*

**Problem:** security questionnaires ask for artifacts; none exist. This step is deliberately **last in its phase** — it documents behavior the earlier steps made true (audit: 17, revocation: 16, backups/RPO: 28, retention: Phase 2 + 17, exports: 40).

**Change — checked-in artifacts:**
1. `SECURITY.md` — vulnerability reporting, supported versions, disclosure policy.
2. Versioning policy + `CHANGELOG.md` — semver, what constitutes breaking, upgrade-note discipline (ties to Step 33 image tags).
3. `docs/data-retention.md` — per data class: metrics (`METRICS_RETENTION_DAYS`, default 90), audit (`AUDIT_RETENTION_DAYS`, default 400), backups (Step 28 retention), traps, with the config knob for each.
4. `docs/runbooks/access-review.md` — quarterly: enumerate users/roles (API), cross-check against the audit log, deactivate stale accounts (deactivation is immediate per Step 16).
5. `docs/runbooks/incident-response.md` — detection (Step 36 alerts), containment (revoke agent Step 19 / lock user / rotate secrets Step 34), evidence (audit export Step 40), recovery (restore Step 28).

**Migration:** none.

**Verify:** a mock security-questionnaire pass (standard SIG-Lite-style questions) answers each applicable question by pointing at a checked-in artifact or a verifiable behavior; no answer requires "we plan to".

**Decision required:** none.

---

# What we are explicitly not building (and what would reopen each)

| Deferred | Why | Reopen trigger |
|---|---|---|
| SSO (OIDC/SAML) + MFA | Local accounts + hardened policy (Steps 15/16/38) cover current deployments | First procurement requiring IdP login |
| Multi-tenancy / MSP isolation | Large data-model change; no concrete requirement | A real multi-team/MSP customer |
| Kubernetes / multi-host HA | Locked single-host platform decision | HA SLA or multi-host requirement |
| Vault/KMS secrets manager | File-based docker secrets suffice on one host (Step 34) | Fleet of deployments to manage centrally |
| OpenTelemetry tracing | Correlation IDs (Step 35) cover debugging at this scale | Cross-service latency issues logs can't resolve |
| Mobile app | Responsive web suffices | — |
| AI root-cause analysis | Insufficient labeled data volume | — |

---

# Recommended next block

**Now:** Step 15 (rate limiting — roadmap 1.3, marked NEXT) → 16 → 17 → 18 → 19, with **Steps 20–21 (CI + lint) started in parallel** so every security step lands under CI.

Resolve before coding the affected step:
- **Step 15:** rate/lockout thresholds (recommend 10/min/IP; 10 failures → 15 min).
- **Step 17:** audit retention (recommend 400 days).
- **Step 18:** dev compose stays HTTP, TLS only in prod overlay (recommended).
- **Step 19:** grace-mode rollout for existing agents (recommended yes, one release).
