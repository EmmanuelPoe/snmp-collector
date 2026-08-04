# Enterprise-Readiness Roadmap

A step-by-step plan to take the SNMP Collector from a solid, feature-complete
application to an enterprise-grade product. Each step lists **why**, **what to do**,
and a **verify** check so progress is measurable.

This document is the **prioritized tracker** — the why, the priority, and the
progress state. The build-level detail (files, migrations, decisions, test plans)
for every step below lives in [implementation-plan.md](implementation-plan.md);
each step here names its implementation-plan step number.

## Product definition & scope (locked 2026-07-09)

Decisions that bound everything below. Revisit only if the trigger listed fires.

| Decision | Choice | Trigger to revisit |
|---|---|---|
| Production platform | **Single-host docker-compose**, hardened (TLS, non-root, limits, backups, restart policies). No Kubernetes/Helm. | A customer needs multi-host HA or an orchestrated platform. |
| Scale target | **1000+ devices**, proven by a committed load-test harness and published benchmark numbers — not just documented limits. | — |
| Compliance | **SOC 2-style audit evidence in scope**: audit logging, retention proof, access-review and incident runbooks, security docs — the artifacts a security questionnaire requests. | — |
| SSO / OIDC / SAML / MFA | **Deferred.** Local accounts (admin/editor/viewer) with hardened password/session policy instead. | First enterprise procurement that requires IdP login. |
| Multi-tenancy / MSP isolation | **Deferred.** Single-org deployments only. | A concrete MSP/multi-team requirement. |

## Progress tracker (resume here)

Work through the tiers in order; check off each step as it lands. Detailed
completion notes live inline under each step below; build specs live in the
implementation plan (step number in parentheses).

- [x] **Step 1.1** — Encrypt SNMP credentials at rest *(done 2026-06-30)*
- [x] **Step 1.2** — Eliminate default/baked-in secrets + enforce rotation *(done 2026-06-30)*
- [x] **Step 1.3** — Rate-limit auth + login lockout *(plan Step 15, done 2026-07-09)*
- [x] **Step 1.4** — Token lifecycle: revocation, logout *(plan Step 16, done 2026-07-09)*
- [x] **Step 1.5** — Audit logging *(plan Step 17, done 2026-07-15)*
- [x] **Step 1.6** — CORS tightening + TLS/HSTS/security headers *(plan Step 18, done 2026-07-15 — `nginx -t` + curl verification pending, needs the Docker stack)*
- [x] **Step 1.7** — Per-agent credentials (retire shared bearer for agents) *(plan Step 19, done 2026-07-15 — grace mode on; flip `AGENT_AUTH_ENFORCE=true` once all agents re-enrolled)*
- [x] **Step 3.1** — CI pipeline *(plan Step 20, done 2026-07-09 — enable branch protection on GitHub to make it merge-blocking)*
- [x] **Step 3.2** — Lint / format / type-check gates *(plan Step 21, done 2026-07-15)*
- [x] **Step 3.3** — Dependency + image scanning, SBOM *(plan Step 22, done 2026-07-19)*
- [x] **Step 3.4** — Secret scanning *(plan Step 23, done 2026-07-19 — history clean, no rotation needed)*
- [x] **Step 3.5** — Frontend + E2E test coverage *(plan Step 24, done 2026-07-19 — Playwright live run pending first CI pass)*
- [x] **Step 2.1** — Agent registry into Postgres *(plan Step 25, done 2026-07-19 — live-stack verification pending Docker)*
- [x] **Step 2.2** — Harden silent failure paths *(plan Step 26, done 2026-07-19)*
- [x] **Step 2.3** — Liveness/readiness + ingest backpressure *(plan Step 27, done 2026-07-19)*
- [x] **Step 2.4** — Backups + tested restore (RPO/RTO) *(plan Step 28, built 2026-07-19 — restore drill itself pending Docker)*
- [x] **Step 2.5** — Load-test harness at 1000 devices *(plan Step 29, harness built 2026-07-19 — run + publish numbers on next Docker session)*
- [ ] **Step 2.6** — Metrics-store decision gate (DuckDB vs TimescaleDB hot path) *(plan Step 30 — **blocked on 2.5's published numbers**)*
- [ ] **Step 4.1** — Non-root containers, least privilege *(plan Step 31)*
- [ ] **Step 4.2** — Resource limits *(plan Step 32)*
- [ ] **Step 4.3** — Production compose profile + install/upgrade runbooks *(plan Step 33)*
- [ ] **Step 4.4** — Single-host secrets handling *(plan Step 34)*
- [ ] **Step 5.1** — Shared structured logging + correlation IDs *(plan Step 35)*
- [ ] **Step 5.2** — Observability overlay: dashboards + alert rules as code *(plan Step 36)*
- [ ] **Step 5.3** — SLO definitions (+ optional OTel) *(plan Step 37)*
- [ ] **Step 6.1** — Password + session policy *(plan Step 38)*
- [ ] **Step 6.2** — RBAC gating audit + pagination caps *(plan Step 39)*
- [ ] **Step 6.3** — Audited data export *(plan Step 40)*
- [ ] **Step 6.4** — Compliance evidence pack *(plan Step 41)*

**How to verify current state before continuing:**
- Backend tests (run locally — the backend image has no pytest): `cd backend && python -m pytest -q` → 192 passed.
- Manager tests (authoritative in-container; local run shows 8 spurious 401-vs-403 failures from a newer local Starlette): `docker-compose build manager && docker-compose run --rm --no-deps -T manager python -m pytest -q` → 80 passed.
- Agent tests: `cd agent && python -m pytest -q` → 3 passed.

**Deploy note for Steps 1.1–1.2:** ✅ applied to the dev stack 2026-07-09 — `.env`
regenerated with strong secrets plus a dedicated Fernet `ENCRYPTION_KEY`, migration
`021` ran (credentials verified ciphertext in Postgres), and agent polling/ingest
verified end-to-end. Note for other deployments: `ENCRYPTION_KEY` must be a valid
**Fernet key** (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`),
not an arbitrary random string — startup fails fast otherwise.

## How this was assessed

First reviewed 2026-06-30 against the code on `main`; revised 2026-07-09 against
`security/tier1-secret-hardening` (HEAD `500b860`) with the scope decisions above
locked in. The system is already strong: six-service architecture with clear
ownership boundaries, pinned dependencies, structured JSON logging, Prometheus
instrumentation, RBAC (admin/editor/viewer), JWT auth with forced first-login
password change, one-time agent enrollment tokens, transactional/deduplicated
ingest, metrics retention, LLDP topology + dependency suppression, trap
correlation, encrypted credentials at rest, startup secret validation, and a real
test suite (29 test files across backend/manager/agent).

The gaps below are what an enterprise security/procurement/SRE review would flag.
They are ordered by **priority tier**, and within each tier the steps are sequenced
so earlier steps unblock later ones.

Legend: 🔴 critical · 🟠 high · 🟡 medium · 🟢 nice-to-have

---

## Tier 1 — Security hardening (do first)

These are the items most likely to fail a security review or cause a breach.

### Step 1.1 — 🔴 Encrypt SNMP credentials at rest ✅ Done (2026-06-30)
Implemented via a Fernet-backed `EncryptedString` SQLAlchemy type (`backend/crypto.py`)
applied to `snmp_community`, `auth_password`, `priv_password`; migration
`021_encrypt_device_credentials` widens the columns to Text and encrypts existing
rows; key comes from `ENCRYPTION_KEY` (falls back to a JWT_SECRET-derived key with a
warning). Covered by `backend/tests/test_crypto.py`.

### Step 1.2 — 🔴 Eliminate default/baked-in secrets and enforce rotation ✅ Done (2026-06-30)
`check_required_secrets()` in both backend (`config.py`) and manager (`config.py`)
aborts startup (called from each service's lifespan) if `JWT_SECRET`/`MANAGER_API_KEY`
is unset, a known placeholder, or under 16 chars; the baked-in `change-me-in-production`
default was removed from `backend/config.py` and `docker-compose.yml`. The bootstrap
admin now gets a random one-time password logged once (`backend/main.py`). `make up`
generates strong secrets into `.env` on first run. Covered by
`backend/tests/test_secret_validation.py` and `manager/tests/test_config.py`.

### Step 1.3 — 🟠 Rate-limit authentication + login lockout ✅ Done (2026-07-09)
Implemented via `slowapi` (`backend/rate_limit.py`): per-IP limit on `/auth/login`
(keyed on nginx's `X-Real-IP`), per-session-token limits on `/auth/change-password`
and `/devices/{id}/walk`; all limits configurable (`LOGIN_RATE_LIMIT`,
`WALK_RATE_LIMIT`, `RATE_LIMIT_ENABLED`). Persistent per-account lockout
(migration `022`: `failed_login_count`/`locked_until` on `users`) returns `423` +
`Retry-After` after `LOGIN_LOCKOUT_THRESHOLD` failures for `LOGIN_LOCKOUT_MINUTES`,
checked before password verification so a locked account leaks no signal; the
frontend surfaces locked/rate-limited states distinctly. Covered by
`backend/tests/test_rate_limit.py` (8 tests) and verified live (429 after 11 rapid
bad logins through nginx; 423 on the locked account). Note: limiter state is
per-uvicorn-worker — the DB-backed lockout is the authoritative brake.

### Step 1.4 — 🟠 Token lifecycle: revocation and logout ✅ Done (2026-07-09)
Implemented via migration `023`: `users.token_version` (embedded as the `ver` JWT
claim, bumped on password change so all prior tokens go stale) plus a
`revoked_tokens` jti denylist for explicit logout, both checked in
`_resolve_user` (`backend/auth.py`). `POST /auth/logout` revokes the presented
token and opportunistically prunes expired denylist rows; change-password now
returns a fresh token so the current session continues while every other session
is invalidated; the frontend revokes server-side on sign-out and adopts the fresh
token after password change. Deactivation was already immediate (`_resolve_user`
filters `is_active`). Covered by `backend/tests/test_token_lifecycle.py` (7 tests)
and verified live (logout → 401; password change → old tokens 401, fresh token 200).

### Step 1.5 — 🟠 Audit logging ✅ Done (2026-07-15)
Implemented via migration `024`: append-only `audit_log` table (actor, action,
target, summary JSON, source IP from `X-Real-IP`, timestamp) written through
`backend/audit.py` `record()` from every mutating router — auth (login
success/failure, logout, password change, user create), devices (CRUD + walk),
config, alerts (resolve/ack/assign/note), alert-rules, notification channels,
maintenance windows, topology discover. Credential values (`snmp_community`,
`auth_password`, `priv_password`, passwords, webhook `url`) are redacted from
summaries; field names remain visible. Admin-only `GET /audit` (paginated,
filterable by actor/action/target/date) + frontend Audit Log page (admin
sidebar). Retention: `AUDIT_RETENTION_DAYS` (default 400) pruned weekly by a
backend lifespan task mirroring the manager's retention loop. Covered by
`backend/tests/test_audit.py` (18 tests). Deploy note: run `make migrate` to
create the table.

### Step 1.6 — 🟡 Tighten CORS and transport security ✅ Done (2026-07-15)
CORS restricted to GET/POST/PUT/DELETE + Authorization/Content-Type
(`backend/main.py`, covered by `backend/tests/test_cors.py`). Security headers
(X-Frame-Options DENY, nosniff, Referrer-Policy, CSP **Report-Only** fitted to
the CRA bundle incl. Google Fonts) in `nginx/security_headers.inc`, included by
both vhosts. TLS is an opt-in overlay so dev `make up` stays zero-config:
`docker-compose -f docker-compose.yml -f docker-compose.tls.yml up -d` swaps in
`nginx/conf.d-tls/default.conf` (80→301→443, HSTS max-age=300 during rollout —
raise to 6 months once stable, `/agent/` route proxying remote agents to the
manager over TLS, keeps the runtime-DNS + `/api/internal/` deny patterns).
Certs at `nginx/certs/` (gitignored); self-signed bootstrap
`scripts/gen_self_signed_cert.sh`; full cert paths in `docs/runbooks/tls.md`.
**Verification pending (Docker was down):** `nginx -t` on both vhosts, curl
checks (301, HSTS headers, `/agent/` claim→ingest), `make simulation`. CSP
enforcement flip is a follow-up after a quiet Report-Only period.

### Step 1.7 — 🟡 Per-agent credentials — retire the shared bearer for agents ✅ Done (2026-07-15)
Manager issues a per-agent secret (`token_urlsafe(32)`) at `/register` and
`/claim`, returned exactly once; only the SHA-256 hash lives on the registry
record (`manager/registry.py`, persists through registry.json reloads). Agents
send `Bearer <agent_id>:<secret>` on heartbeat/config/ingest/command routes,
verified constant-time by `require_agent_auth` (`manager/auth.py`); an agent
can only act as itself (403 otherwise), and a command result is only accepted
from the agent the command targets. Deregister = instant revocation. Agent
persists the secret 0600 next to its ID file (`agent/credentials.py`);
`MANAGER_API_KEY` is now optional for agents — claim-token enrollments never
hold it (dev compose keeps it for the `/register` bootstrap only). **Grace
mode:** `AGENT_AUTH_ENFORCE=false` (default) still accepts the shared key on
agent routes with a warning; flip to `true` once every agent has re-enrolled.
Operator/backend routes (`/register`, agent list, deregister, enqueue-command,
`/commands/{id}` polling) keep the shared key; backend internal endpoints
reject agent credentials by construction. Tests:
`manager/tests/test_agent_auth.py` (10) + `agent/tests/test_credentials.py` (4).
**Verification pending (Docker down):** in-container manager suite, `make simulation`.

---

## Tier 3 — CI/CD, quality gates & supply chain

Numbered Tier 3 but **starts in parallel with Tier 1** — CI protects every change
that follows.

### Step 3.1 — 🔴 Add a CI pipeline ✅ Done (2026-07-09)
`.github/workflows/ci.yml`: five jobs on every PR/push-to-main — backend pytest
(local pip), manager pytest (in-container, authoritative), agent pytest, all-image
build, and the `make simulation` e2e smoke test (compose logs uploaded as artifact
on failure). Along the way this repaired `scripts/run_simulation.sh`, which had
been silently broken by Steps 1.2/1.4 (hardcoded `changeme` password; discarded
the fresh post-password-change token) — it now parses the one-time bootstrap
password from the backend log or accepts `SIM_ADMIN_EMAIL`/`SIM_ADMIN_PASSWORD`,
and adopts the fresh token. Verified locally end-to-end.
**Remaining manual step:** enable branch protection on `main` in GitHub settings
requiring these five checks, to make CI merge-blocking.

### Step 3.2 — 🟠 Linting, formatting, and type checking as gates ✅ Done (2026-07-15)
Root `pyproject.toml`: ruff for lint **and** format (defaults + isort + W;
E711/E712 ignored — SQLAlchemy filter idiom; E402 allowed in tests) and mypy
per service, lenient baseline — untyped-SQLAlchemy/pydantic noise codes
disabled with a written ratchet plan (pydantic plugin → Mapped[] models →
check_untyped_defs). Frontend: `.prettierrc` + prettier pinned as devDependency;
eslint via CRA's `react-app` config at zero warnings. `.pre-commit-config.yaml`
(ruff-check, ruff-format, prettier, eslint) — `pre-commit run --all-files`
passes. Dedicated format-only commit `b8c45ec` (131 files) keeps the mechanical
churn out of functional history. New CI `lint` job runs all five checks
(ruff check/format, mypy ×3 services, prettier, eslint). Verified locally: an
injected violation fails both ruff (F821) and mypy (name-defined); all three
pytest suites + the frontend build re-ran green after the format pass.

### Step 3.3 — 🟠 Dependency and container vulnerability scanning ✅ Done (2026-07-19)
CI `dependency-audit` job: `pip-audit` per service (full-resolution) +
`npm audit --omit=dev --audit-level=high`; `build-images` now Trivy-scans the
five built images (**fail on fixable HIGH/CRITICAL**, `--ignore-unfixed`;
exceptions in `.trivyignore` with reason + expiry) and uploads a syft SPDX SBOM
per image as the `image-sboms` artifact. `.github/dependabot.yml`: pip ×3, npm,
docker ×5, github-actions, weekly. **Existing findings fixed by bumping pins**
(validated: all suites + frontend build green under the new versions):
fastapi 0.109.1, cryptography 48.0.1, python-multipart 0.0.31 (backend);
pyarrow 23.0.1, python-multipart 0.0.31, jinja2 3.1.6, pytest 9.0.3,
pytest-asyncio 1.3.0 (manager/agent); `npm audit fix` (form-data, react-router).
One allowlist entry: PYSEC-2026-2263 (pyasn1 0.4.8 — fix breaks pysnmp 4.4.12;
expires 2026-10-31; clearing it = agent pysnmp migration + `make simulation`).
**Pending on CI/Docker:** Trivy/syft run (needs built images), in-container
manager suite + e2e under the bumped pins, Dependabot PRs appearing.

### Step 3.4 — 🟡 Secret scanning ✅ Done (2026-07-19)
gitleaks v8.24.3 as a pre-commit hook and a CI `secret-scan` job (full-history
scan every run — small repo, strictly stronger than diff scans).
**One-time history scan performed 2026-07-19**: 187 commits, 8 findings, all
confirmed dummy values (test fixtures + the `.env.example` placeholder) — zero
real secrets, nothing to rotate. Those exact values are allowlisted in
`.gitleaks.toml` (policy in-file: never allowlist a real credential — rotate).
Verified an injected realistic AWS key pair is caught. Gitignore audit:
`.env`, `data/`, `nginx/certs/` covered, **but `data/db/metrics.db` had been
force-added historically — now untracked** (`git rm --cached`); old dev-data
copies remain in history (no credentials, acceptable per the
rotate-don't-rewrite policy).

### Step 3.5 — 🟡 Frontend and integration test coverage ✅ Done (2026-07-19)
Testing-library added (react 14 / jest-dom 6 / user-event 14, pinned).
10 component tests across the three critical flows: login
(success/failure/lockout-423/forced password change), device modal (create,
create-with-thresholds → alert-rule upsert, edit) and the dashboard alert feed
(render + viewer gating, acknowledge, assign) — API mocked at the
`services/api` boundary. Coverage floor enforced via jest `coverageThreshold`
in `frontend/package.json` (starts at 22/15/13/23 %stmts/branch/func/lines —
ratchet up, never down) through the new CI `frontend-tests` job. Playwright
happy-path E2E (`e2e/smoke.spec.js`): bootstrap login → forced password change
→ add simulator device → poll until metrics arrive → chart renders; wired into
the CI e2e job *before* `run_simulation.sh` (Playwright consumes the one-time
bootstrap password, sets a known one, the simulation reuses it).
**Pending on CI/Docker:** first live Playwright run against the compose stack.

---

## Tier 2 — Reliability & scale (single host, 1000+ devices)

Reframed for the locked scope: the goal is **durability and a benchmarked
1000-device ceiling on one host**, not multi-node HA.

### Step 2.1 — 🟠 Move the agent registry into Postgres ✅ Done (2026-07-19)
Backend Alembic migration `025` creates `agent_registry` (schema owned by the
single migration authority; **data owned by the manager** — the documented
mirror of the DuckDB arrangement). `DbAgentRegistry` in `manager/registry.py`:
SQLAlchemy Core (no ORM), in-memory dict stays the read path, per-agent
upsert/delete on change, full `SELECT` at startup; DB errors degrade to
warnings (memory stays authoritative, next heartbeat retries) so a late
Postgres never crashes the manager. Selected via `REGISTRY_BACKEND`
(`file` default for unit tests/bare runs; compose sets `postgres` +
`DATABASE_URL` + `depends_on: postgres healthy`). Enrollment slots stay
in-memory by design (TTL'd one-time tokens). Tests:
`manager/tests/test_registry_db.py` (5 — upsert/reload, heartbeat persist,
deregister, claim-path hash, unreachable-DB degradation) against a SQLite URL.
**Pending on Docker:** `make migrate` (024+025), e2e with the postgres
backend, volume-wipe survival check, pg_dump inclusion.

### Step 2.2 — 🟠 Harden silent failure paths ✅ Done (2026-07-19)
All four swallow-alls narrowed and loud:
- `manager/db.py _migrate`: only `duckdb.CatalogException` (fresh DB) is
  expected; anything else logs ERROR and re-raises — corruption aborts startup.
- `backend/main.py` bootstrap: `OperationalError` now logs ERROR and
  propagates — a dead Postgres fails startup instead of reporting healthy
  (compose healthcheck/restart handles boot ordering). This exposed that the
  swallow had been masking a missing-schema gap in the test bootstrap DB,
  now fixed in `backend/tests/conftest.py` (create_all + stale file removed).
- `manager/registry.py` file backend: corrupt JSON logs ERROR and is
  **quarantined to `registry.corrupt`** for inspection instead of vanishing.
- `agent/uploader.py`: every upload failure logs — permanent-looking 4xx
  (401/403/413…, not 429) at ERROR ("needs operator attention"), transient at
  WARNING; both buffers share the helper; queueing behavior unchanged.
Tests: backend `test_startup_failures.py`, manager corrupt-quarantine test,
agent 401-ERROR + network-WARNING caplog tests (suites: 193/90/9).

### Step 2.3 — 🟠 Liveness/readiness split + ingest backpressure ✅ Done (2026-07-19)
Backend: `/health/live` (static, `/health` stays an alias) + `/health/ready`
(Postgres `SELECT 1` hard; manager reachability reported but non-fatal — the
backend proxies metrics over HTTP rather than reading DuckDB directly, so the
spec's "DuckDB read probe" maps to the manager hop). Manager: `/health/live` +
`/health/ready` (DuckDB `SELECT 1` **through the write lock** — saturation
reads as unready, which is the honest signal — plus registry-DB probe when on
the postgres backend; response includes `write_queue` depth). Compose
healthchecks on all seven services (frontend/nginx busybox wget, simulator
real `snmpget`, agent freshness of `/tmp/agent-alive` touched by the heartbeat
loop; backend/manager point at `/health/ready`). Backpressure: waiter counter
around the DuckDB write lock (`INGEST_MAX_QUEUE`, default 8); `/ingest` sheds
load with `503 + Retry-After: 30` from a route dependency (before body parse);
the agent logs 503 at INFO as an expected deferral and its disk queue absorbs
it. Tests: backend health ×3, manager health/backpressure ×3, agent 503-INFO.
**Pending on Docker:** `docker ps` health states, stop-postgres readiness
flip, saturation drill with row-count reconciliation (Step 2.5 harness).

### Step 2.4 — 🔴 Backups and tested restore (RPO/RTO) ✅ Built (2026-07-19) — restore drill pending Docker
`make backup` → `scripts/backup.sh`: `pg_dump -Fc` (everything relational incl.
agent registry + credential hashes) + DuckDB snapshot via the manager's new
`POST /internal/backup` (shared-key auth; CHECKPOINT + copy **inside the write
lock**, so consistent under live ingest — deferrals absorbed by 2.3
backpressure). Timestamped pairs in `./backups/` (gitignored, bind-mounted),
retention newest 14 (`BACKUP_KEEP`), daily host-cron recipe documented.
`make restore BACKUP=<ts>` → `scripts/restore.sh` (stop writers,
`pg_restore --clean --if-exists`, swap DuckDB file, restart).
`docs/runbooks/restore.md`: **RPO = backup interval (24 h default), RTO ≤ 30
min**, verify checklist (incl. the after-backup-gap proof), quarterly drill
feeding the 6.4 evidence pack. Tests: snapshot validity (opens read-only,
expected tables) + auth. **Pending on Docker: the actual restore drill.**

### Step 2.5 — 🔴 Load-test harness at the 1000-device target ✅ Harness built (2026-07-19) — numbers pending first run
`make loadtest` = `scripts/loadtest/ingest_load.py` (4 synthetic agents pushing
agent-sized Parquet batches through the real `/ingest`; reports rows/s, upload
p50/p99, 503 deferrals, errors — batch generator verified against the agent's
exact schema) + `scripts/loadtest/query_load.py` (8 dashboard-like readers +
exporter scrape; query p50/p99) + a `docker stats` snapshot (feeds 4.2 limits).
The alert evaluator now logs its loop duration (WARN when it blows the 30 s
cadence). Recipe + results table: `docs/scale-benchmark.md` —
**run it on the next Docker session and publish the numbers; Step 2.6 is
blocked on them.**

### Step 2.6 — 🔴 Metrics-store decision gate *(plan Step 30)*
**Why:** All manager writes serialize through one global lock on a single DuckDB
file, and the backend mounts the same file read-only. Whether that holds at 1000
devices is an empirical question — decide from 2.5's numbers, not intuition.
**What to do:** Against pre-stated pass/fail criteria, either (a) keep DuckDB and
tune (batching, partitioning), or (b) move the hot metrics path to TimescaleDB
(already in the stack) and keep DuckDB for columnar batch. Document the chosen
ceiling and the migration path either way.
**Verify:** Documented, benchmarked ingest/query throughput at the target device
count; the load test sustains it without lock starvation.

---

## Tier 4 — Deployment & operations (single-host production)

### Step 4.1 — 🟠 Run all containers as non-root with least privilege *(plan Step 31)*
**Why:** Only `manager/Dockerfile` creates and switches to a non-root `app` user.
Backend, agent, and frontend images run as root.
**What to do:** Add a non-root `USER` to every Dockerfile, drop Linux capabilities,
set `read_only` root filesystems where possible. Note: the agent binds UDP 162 for
traps — default to a high port and grant `NET_BIND_SERVICE` only when 162 is required.
**Verify:** `docker inspect`/`id` in each running container shows a non-root UID; traps
still received.

### Step 4.2 — 🟠 Resource limits and quotas *(plan Step 32)*
**Why:** No CPU/memory limits in `docker-compose.yml`; a runaway service can
starve the host.
**What to do:** Set per-service CPU/memory limits in the production overlay, sized
from the 2.5 load-test data.
**Verify:** A synthetic load does not let one service exhaust host memory; limits are
documented.

### Step 4.3 — 🟠 Production compose profile + install/upgrade runbooks *(plan Step 33)*
**Why:** One `docker-compose.yml` serves both dev and "production"; there is no
hardened production posture (TLS, restart policies, log rotation, closed ports) and
no install/upgrade procedure. This replaces the earlier Kubernetes/Helm idea per
the locked platform decision.
**What to do:** Add a `docker-compose.prod.yml` overlay: TLS nginx (1.6), restart
policies, log rotation, unpublished internal ports, pinned image tags, resource
limits (4.2). Write install, upgrade, and rollback runbooks.
**Verify:** A clean host reaches a healthy stack by following the install runbook
alone; an upgrade + rollback drill succeeds.

### Step 4.4 — 🟡 Single-host secrets handling *(plan Step 34)*
**Why:** Secrets live in a flat `.env` file readable by anyone who can read the
compose directory; rotation is manual and undocumented.
**What to do:** Move `JWT_SECRET`, `ENCRYPTION_KEY`, `MANAGER_API_KEY`, and DB
credentials to docker-compose `secrets:` (file-based, root-owned) with `*_FILE`
support in each service's config; document the rotation procedure per secret. A
full secrets manager (Vault etc.) is out of scope for single-host.
**Verify:** No secret material in `docker-compose*.yml`, images, or world-readable
files; each documented rotation procedure works without data loss.

---

## Tier 5 — Observability & SRE

### Step 5.1 — 🟠 Shared structured logging + correlation IDs *(plan Step 35)*
**Why:** JSON logging exists but is ad-hoc `json.dumps` duplicated across seven
modules in three services, with no shared schema and no way to follow one request
across backend→manager→agent.
**What to do:** Extract a shared JSON formatter (standard fields: `service`,
`level`, `correlation_id`, …), generate/propagate a correlation ID across service
calls and agent uploads, and emit it in every log line.
**Verify:** A single upload can be followed end-to-end across services by one
correlation ID; all services emit the same log schema.

### Step 5.2 — 🟡 Observability overlay: dashboards + alert rules as code *(plan Step 36)*
**Why:** Metrics are exposed but there are no checked-in dashboards or platform
alert rules. Also fixes the docs/compose drift: `.env.example` references a
`docker-compose.observability.yml` (and a Grafana password) that don't exist, and
`observability/` holds only an empty `loki/` dir.
**What to do:** Ship the observability overlay for real: Prometheus + Grafana with
provisioned dashboards + Loki for logs, plus committed Prometheus alert rules for
the platform itself (ingest freshness, queue depth, agent offline, DuckDB write
latency, disk usage).
**Verify:** `docker-compose -f docker-compose.yml -f docker-compose.observability.yml up`
provisions dashboards automatically; a simulated ingest stall fires the freshness
alert; every file referenced in README/`.env.example` exists.

### Step 5.3 — 🟢 SLO definitions (+ optional OpenTelemetry) *(plan Step 37)*
**Why:** No SLOs exist, so "is it healthy enough?" has no answer; OTel tracing is
valuable but not a blocker once correlation IDs (5.1) land.
**What to do:** Define SLOs (ingest freshness, API p99, evaluator lateness) with
error budgets and recording rules; add OTel tracing only if debugging outgrows
correlation IDs.
**Verify:** SLO dashboards show budget burn; a simulated breach is visible.

---

## Tier 6 — Governance & compliance

SSO moved out of scope (see Product definition) — these steps make local accounts
and data handling enterprise-defensible instead.

### Step 6.1 — 🟠 Password and session policy *(plan Step 38)*
**Why:** Password policy is `min_length=8` only (`backend/routers/auth.py:27`);
no complexity rules, no idle-session timeout.
**What to do:** Enforce configurable password complexity + common-password
rejection; add idle-session timeout (building on the 1.4 token lifecycle);
account lockout arrives with 1.3.
**Verify:** Weak passwords are rejected on change/create; idle sessions expire per
config.

### Step 6.2 — 🟡 RBAC gating audit + pagination caps *(plan Step 39)*
**Why:** Three roles exist (`admin`/`editor`/`viewer`, `backend/models.py:48`) but
there is no documented route→role matrix to review. List endpoints are unbounded:
`/alerts` has **no pagination at all** (`backend/routers/alerts.py:19-28`) and
`/devices` accepts any `limit`.
**What to do:** Produce and test a route→role matrix (every mutating route gated
as intended); enforce pagination + max page size on every list endpoint.
**Verify:** A viewer cannot mutate anything; an editor cannot manage users; large
list queries are bounded.

### Step 6.3 — 🟡 Audited data export *(plan Step 40)*
**Why:** Metrics CSV export exists (Phase 2), but alerts and audit logs have no
export path, and exports leave no trace — compliance reviews ask for both.
**What to do:** Add export endpoints for alerts and audit logs; every export
(including the existing metrics CSV) writes an audit row.
**Verify:** Export produces a complete artifact and a corresponding audit entry.

### Step 6.4 — 🟡 Compliance evidence pack *(plan Step 41)*
**Why:** Security questionnaires ask for artifacts, not intentions: vulnerability
disclosure policy, retention statements, access-review process, incident response,
versioning/support policy. None exist.
**What to do:** Write and check in: `SECURITY.md`, versioning policy + `CHANGELOG.md`,
per-data-class retention statement, access-review runbook (quarterly, driven by the
audit log), incident-response runbook.
**Verify:** A mock security-questionnaire pass answers every standard question by
pointing at a checked-in artifact.

---

## Suggested execution order

1. **Tier 1** (security) — 1.3 → 1.4 → 1.5 → 1.6 → 1.7; start **3.1 + 3.2** (CI, lint)
   in parallel — they protect everything after.
2. **Tier 3** remainder (3.3–3.5) as CI matures.
3. **Tier 2** durability first (2.1 → 2.2 → 2.3 → 2.4), then the scale proof
   (2.5 → 2.6) — the decision gate needs the harness.
4. **Tier 4** production posture (4.1 → 4.2 → 4.3 → 4.4); 4.2/4.3 consume the 2.5
   load-test numbers.
5. **Tier 5** observability (5.1 → 5.2 → 5.3).
6. **Tier 6** compliance pack last (6.1 → 6.2 → 6.3 → 6.4) — it depends on audit
   logging (1.5), token lifecycle (1.4), and retention/backup facts (2.4) being true
   before they are documented as evidence.

Each step is independently shippable and verifiable. Treat the 🔴 items as release
blockers for an "enterprise" label; 🟠 as fast-follows; 🟡/🟢 as backlog to prioritize
against customer demand.
