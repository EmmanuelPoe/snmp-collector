# Enterprise-Readiness Roadmap

A step-by-step plan to take the SNMP Collector from a solid, feature-complete
application to an enterprise-grade product. Each step lists **why**, **what to do**,
and a **verify** check so progress is measurable.

## Progress tracker (resume here)

Work through the tiers in order; check off each step as it lands. Detailed
completion notes live inline under each step below.

- [x] **Step 1.1** — Encrypt SNMP credentials at rest *(done 2026-06-30)*
- [x] **Step 1.2** — Eliminate default/baked-in secrets + enforce rotation *(done 2026-06-30)*
- [ ] **Step 1.3** — Rate-limit authentication and sensitive endpoints ← **NEXT**
- [ ] **Step 1.4** — Token lifecycle: revocation, refresh, logout
- [ ] **Step 1.5** — Audit logging
- [ ] **Step 1.6** — Tighten CORS + transport security (TLS/HSTS)
- [ ] **Step 1.7** — Per-agent service-to-service auth (retire shared bearer)
- [ ] Tiers 2–6 — see sections below

**How to verify current state before continuing:**
- Backend tests (run locally — the backend image has no pytest): `cd backend && python -m pytest -q` → 156 passed.
- Manager tests (authoritative in-container; local run shows 8 spurious 401-vs-403 failures from a newer local Starlette): `docker-compose build manager && docker-compose run --rm --no-deps -T manager python -m pytest -q` → 80 passed.
- Agent tests: `cd agent && python -m pytest -q` → 3 passed.

**Deploy note for Steps 1.1–1.2 (not yet applied to a running stack):**
- Set strong `JWT_SECRET` + `MANAGER_API_KEY` (≥16 chars, non-placeholder) and optionally a dedicated `ENCRYPTION_KEY`, then run `make migrate` so migration `021` encrypts existing device credentials. The current dev `.env` has a weak `JWT_SECRET` and no `MANAGER_API_KEY`, so the backend/manager will refuse to start until it is fixed (delete `.env` and `make up` to regenerate, or edit it).

## How this was assessed

Reviewed on 2026-06-30 against the code on `main`. The system is already strong:
six-service architecture with clear ownership boundaries, pinned dependencies,
structured JSON logging, Prometheus instrumentation, RBAC (admin/viewer), JWT auth
with forced first-login password change, transactional/deduplicated ingest, metrics
retention, LLDP topology + dependency suppression, trap correlation, and a real test
suite (26 test files across backend/manager/agent).

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
**Why:** `Device.snmp_community`, `auth_password`, and `priv_password`
(`backend/models.py:15,23,25`) are stored as plaintext `String(255)`. A read of the
Postgres volume or a SQL-injection/backup leak exposes every device credential.
**What to do:**
- Introduce an application-level encryption layer (e.g. `cryptography` Fernet, or
  envelope encryption backed by a KMS). Add an `ENCRYPTION_KEY` setting sourced from
  a secrets manager, not `.env`.
- Add SQLAlchemy `TypeDecorator` (e.g. `EncryptedString`) so encrypt/decrypt is
  transparent to routers. Apply to the three credential columns.
- Write an Alembic data-migration that encrypts existing rows.
- Ensure credentials are never logged and are redacted in API responses/schemas.
**Verify:** New device write stores ciphertext (inspect row in `make shell-db`);
agent still polls successfully; a unit test asserts round-trip encrypt/decrypt and
that the raw column is not human-readable.

### Step 1.2 — 🔴 Eliminate default/baked-in secrets and enforce rotation ✅ Done (2026-06-30)
`check_required_secrets()` in both backend (`config.py`) and manager (`config.py`)
aborts startup (called from each service's lifespan) if `JWT_SECRET`/`MANAGER_API_KEY`
is unset, a known placeholder, or under 16 chars; the baked-in `change-me-in-production`
default was removed from `backend/config.py` and `docker-compose.yml`. The bootstrap
admin now gets a random one-time password logged once (`backend/main.py`). `make up`
generates strong secrets into `.env` on first run. Covered by
`backend/tests/test_secret_validation.py` and `manager/tests/test_config.py`.
**Why:** `MANAGER_API_KEY` and admin creds default to guessable values
(`docker-compose.yml:35,83` → `change-me-in-production`; bootstrap admin
`admin@localhost / changeme` in `backend/main.py:46-55`). `JWT_SECRET` is required
but `.env.example` ships a placeholder.
**What to do:**
- Fail fast at startup if `MANAGER_API_KEY`, `JWT_SECRET`, or `ENCRYPTION_KEY` equal a
  known-default/placeholder or are shorter than N bytes.
- Generate the bootstrap admin password randomly and print it once (never a fixed
  `changeme`); keep `force_password_change=True`.
- Document a rotation procedure for `MANAGER_API_KEY` and `JWT_SECRET`.
**Verify:** Starting a container with a default secret aborts with a clear error;
fresh install logs a unique one-time admin password.

### Step 1.3 — 🟠 Rate-limit authentication and sensitive endpoints
**Why:** No rate limiting exists (`grep` for slowapi/ratelimit returns nothing).
`/auth/login` is brute-forceable.
**What to do:** Add per-IP + per-account rate limiting (e.g. `slowapi` or nginx
`limit_req`) on `/auth/login`, password-change, and MIB-browser/walk endpoints.
Add exponential backoff / temporary lockout after repeated failures.
**Verify:** Automated test issues N rapid bad logins and receives `429` after the
threshold.

### Step 1.4 — 🟠 Token lifecycle: revocation, refresh, and logout
**Why:** JWTs are stateless with an 8h lifetime and no revocation
(`backend/auth.py:27-29`). A leaked/deactivated user's token stays valid until expiry;
there is no logout invalidation.
**What to do:** Add short-lived access tokens + rotating refresh tokens, or a
server-side token/session denylist (JWT `jti`) so logout and user-deactivation
immediately invalidate. Include a `token_version` on `User` bumped on password change.
**Verify:** After logout or deactivation, the previously issued token is rejected;
password change invalidates old tokens.

### Step 1.5 — 🟠 Audit logging
**Why:** No audit trail exists (`grep audit` → nothing). Enterprises require "who did
what, when" for logins, device/credential changes, config edits, and alert
acknowledgements.
**What to do:** Add an append-only `audit_log` table (actor, action, target, before/
after summary, IP, timestamp) written from mutating routers. Expose an admin-only,
filterable audit view. Ensure logs are tamper-evident (append-only, retained).
**Verify:** Creating/editing/deleting a device and logging in each produce audit rows
with the acting user and source IP.

### Step 1.6 — 🟡 Tighten CORS and transport security
**Why:** CORS allows all methods and headers (`backend/main.py:80-82`); nginx serves
plain HTTP on :80 only (`nginx/conf.d/default.conf`), no TLS.
**What to do:** Restrict CORS methods/headers to what the SPA uses. Add TLS
termination (nginx 443 + HSTS, redirect 80→443) with a documented cert-management
path (Let's Encrypt / corporate CA). Add security headers (CSP, X-Frame-Options,
X-Content-Type-Options).
**Verify:** `curl -I https://…` shows HSTS + security headers; HTTP redirects to HTTPS;
disallowed CORS method is rejected.

### Step 1.7 — 🟡 Service-to-service auth beyond a shared bearer
**Why:** Agent↔Manager↔Backend all share one static `MANAGER_API_KEY`
(`manager/auth.py`, `backend/auth.py:81-86`). One leak compromises all hops, and it
never rotates.
**What to do:** Move to per-agent tokens/certs (mTLS on the internal network, or
per-agent API keys issued at registration and revocable). Scope the backend's internal
endpoints so only the manager identity can call them.
**Verify:** Revoking one agent's credential blocks only that agent; a stolen agent key
cannot call backend internal endpoints.

---

## Tier 2 — Reliability, HA & scalability

### Step 2.1 — 🔴 Remove the JSON-file registry single point of failure
**Why:** The manager persists agent registry to a single JSON file
(`manager/registry.py:85` writes `registry.json`). This prevents running more than one
manager, is race-prone, and loses state on volume loss.
**What to do:** Move the registry into a shared datastore (Postgres or Redis) so
managers are stateless and horizontally scalable. Keep the file as a fallback only for
single-node dev.
**Verify:** Two manager replicas share registry state; killing one does not lose agent
registrations.

### Step 2.2 — 🟠 Address DuckDB single-writer scaling ceiling
**Why:** All manager writes serialize through one global `asyncio.Lock` on a single
DuckDB file (`manager/db.py:8,67`), and the backend mounts the same file read-only.
This is a hard vertical ceiling and couples backend availability to the file.
**What to do:** Decide the scaling target and pick one: (a) partition/sharded DuckDB
per agent-group, (b) move hot metrics to TimescaleDB (already in the stack) for the
query path while keeping DuckDB for columnar batch, or (c) a dedicated OLAP store
(ClickHouse) if volume warrants. Document the chosen ceiling and migration path.
**Verify:** Documented, benchmarked ingest/query throughput at target device count;
load test sustains it without lock starvation.

### Step 2.3 — 🟠 Replace bare `except: pass` and harden failure paths
**Why:** `manager/db.py:44-45` swallows all exceptions during schema migration; the
bootstrap block in `backend/main.py:56-57` swallows `OperationalError`. Silent failures
hide corruption.
**What to do:** Narrow exception handling, log at WARNING/ERROR with context, and fail
loudly where a corrupt/locked DB should stop startup rather than continue.
**Verify:** Injecting a migration error surfaces a logged, actionable message instead
of silent continuation.

### Step 2.4 — 🟠 High-availability Postgres and backups
**Why:** Single Postgres instance (`docker-compose.yml:4-21`), no backup/restore or
PITR strategy for Postgres *or* the DuckDB metrics file.
**What to do:** Document and script: automated `pg_dump`/PITR backups, DuckDB file
snapshotting, tested restore runbook, and (for prod) a replicated/managed Postgres.
**Verify:** A scheduled backup runs; a restore drill reconstructs data to a point in
time.

### Step 2.5 — 🟡 Graceful shutdown, readiness vs liveness, and backpressure
**Why:** Backend has no compose healthcheck (only manager/postgres do). No distinction
between liveness and readiness (readiness should gate on DB reachability). No
backpressure signal when ingest lags.
**What to do:** Add `/health/live` and `/health/ready` (ready checks Postgres/DuckDB).
Add backend + agent + frontend healthchecks in compose. Return `503`/retry-after from
`/ingest` when the write lock/queue is saturated so agents back off.
**Verify:** Killing Postgres flips readiness to unhealthy but liveness stays up;
saturated ingest returns a retryable status and the agent queues rather than drops.

---

## Tier 3 — CI/CD, quality gates & supply chain

### Step 3.1 — 🔴 Add a CI pipeline
**Why:** No `.github/workflows` exists. Nothing runs tests, lint, or builds on a PR.
**What to do:** Add CI (GitHub Actions) that on every PR: installs deps, runs the full
pytest suite (backend/manager/agent), builds all images, and runs the
`make simulation` end-to-end smoke test against the simulator. Block merge on failure.
**Verify:** A PR that breaks a test is red and unmergeable; a green PR shows all suites
passing.

### Step 3.2 — 🟠 Linting, formatting, and type checking as gates
**Why:** No `ruff`/`black`/`mypy`/`eslint`/`prettier` config present. Style and type
drift accumulate.
**What to do:** Add `ruff` + `black` + `mypy` for Python and `eslint` + `prettier` for
the React app, with a `pyproject.toml`/config checked in and a `pre-commit` config.
Wire them into CI.
**Verify:** CI fails on a lint/type violation; `pre-commit run --all-files` passes
locally.

### Step 3.3 — 🟠 Dependency and container vulnerability scanning
**Why:** Deps are pinned (good) but nothing scans them. No SBOM.
**What to do:** Enable Dependabot/Renovate, run `pip-audit` + `npm audit` and image
scanning (Trivy/Grype) in CI, and generate an SBOM per image. Add a policy for
severity thresholds that block release.
**Verify:** A known-vulnerable pinned dep triggers a CI failure/alert; SBOM artifact is
produced per build.

### Step 3.4 — 🟡 Frontend and integration test coverage
**Why:** `frontend/src` has no tests; E2E is a manual `make simulation`.
**What to do:** Add React component/interaction tests (Vitest/RTL) for the critical
flows (login, device CRUD, alert feed) and a Playwright happy-path E2E in CI. Track
coverage with a floor that ratchets up.
**Verify:** CI reports frontend coverage; Playwright login→device→metrics flow passes
headless.

### Step 3.5 — 🟡 Secret scanning
**Why:** `.env` is present in the working tree; risk of committed secrets.
**What to do:** Add `gitleaks`/`trufflehog` to CI and pre-commit; confirm `.env` and
`data/` are gitignored; scrub any historical secrets.
**Verify:** CI blocks a PR that introduces a secret-looking string.

---

## Tier 4 — Deployment & operations

### Step 4.1 — 🟠 Run all containers as non-root with least privilege
**Why:** Only `manager/Dockerfile` creates and switches to a non-root `app` user.
Backend, agent, and frontend images run as root.
**What to do:** Add a non-root `USER` to every Dockerfile, drop Linux capabilities,
set `read_only` root filesystems where possible, and use multi-stage builds to shrink
images. Note: the agent binds UDP 162 for traps — grant only `NET_BIND_SERVICE` or map
to a high port.
**Verify:** `docker inspect`/`id` in each running container shows a non-root UID; traps
still received.

### Step 4.2 — 🟠 Resource limits and quotas
**Why:** No CPU/memory limits in `docker-compose.yml`; a runaway agent or ingest can
starve the host.
**What to do:** Set `cpus`/`mem_limit` (compose) or requests/limits (K8s) per service,
sized from observed usage.
**Verify:** A synthetic load does not let one service exhaust host memory; limits are
documented.

### Step 4.3 — 🟠 Kubernetes/Helm deployment path
**Why:** Only `docker-compose.yml` exists — fine for a single host, but enterprises
deploy on orchestrated platforms with HA, rolling updates, and secrets integration.
**What to do:** Provide a Helm chart (or Kustomize) with Deployments/StatefulSets,
HPA, PodDisruptionBudgets, secret references (External Secrets/Vault/CSI),
persistent volumes for Postgres/DuckDB, and network policies. Keep compose for local
dev.
**Verify:** `helm install` brings up the stack on a test cluster; rolling update causes
no request loss.

### Step 4.4 — 🟡 Fix docs/compose drift
**Why:** `.env.example:44-45` and the README reference
`docker-compose.observability.yml` and Grafana, but that file is absent from the repo.
**What to do:** Either add the observability compose overlay (Prometheus + Grafana with
provisioned dashboards) or remove the dangling references. There is a `prometheus/`
dir with `snmp.yml` that should be reconciled with the actual scrape config.
**Verify:** Every file/command referenced in README and `.env.example` exists and works
as documented.

### Step 4.5 — 🟡 Centralized secrets management
**Why:** Secrets live in `.env`/environment variables.
**What to do:** Integrate a secrets manager (Vault, AWS/GCP Secrets Manager, or K8s
External Secrets). Inject `ENCRYPTION_KEY`, `JWT_SECRET`, `MANAGER_API_KEY`, and DB
creds at runtime, never from a checked-in file.
**Verify:** No secret material is present in images, compose files, or the repo; app
reads secrets from the manager at boot.

---

## Tier 5 — Observability & SRE

### Step 5.1 — 🟠 Distributed tracing and correlation IDs
**Why:** JSON logging exists (`backend/main.py:21-38`) and Prometheus is instrumented,
but there is no request/trace correlation across backend→manager→agent.
**What to do:** Add OpenTelemetry tracing with a propagated trace/correlation ID
through the ingest and query paths; emit it in every log line. Export to an OTLP
collector.
**Verify:** A single upload can be followed end-to-end across services by one trace ID.

### Step 5.2 — 🟡 Dashboards, SLOs, and alerting-as-code
**Why:** Metrics are exposed but there are no checked-in dashboards, SLO definitions,
or alert rules for the platform itself (ingest lag, queue depth, agent offline,
DuckDB write latency).
**What to do:** Commit Grafana dashboards + Prometheus alert rules as code; define SLOs
(e.g. ingest freshness, API p99, alert-evaluator lateness) with error budgets.
**Verify:** Dashboards provision automatically; a simulated ingest stall fires the
freshness alert.

### Step 5.3 — 🟡 Structured logging consistency + log shipping
**Why:** Confirm all three Python services use the same JSON schema and ship to a
central store (ELK/Loki) with retention.
**What to do:** Extract the JSON formatter into a shared module, standardize fields
(service, trace_id, actor), and document a log-shipping setup.
**Verify:** Logs from all services share one schema and are queryable centrally.

---

## Tier 6 — Enterprise features & governance

### Step 6.1 — 🟠 SSO / OIDC / SAML and MFA
**Why:** Auth is local username/password only. Enterprises require SSO and MFA.
**What to do:** Add OIDC/SAML integration (Okta/Entra/Google) with group→role mapping,
and TOTP/WebAuthn MFA for local accounts. Keep local admin as a break-glass account.
**Verify:** A user logs in via the IdP and is mapped to the correct role; MFA is
enforceable per policy.

### Step 6.2 — 🟡 Finer-grained RBAC and (optional) multi-tenancy
**Why:** Only `admin`/`viewer` roles exist (`backend/models.py:46`). Large orgs need
operator/read-only/per-team scoping; MSPs need tenant isolation.
**What to do:** Expand roles (e.g. operator, auditor) and gate each mutating route
accordingly. Evaluate whether device/alert data must be partitioned per team/tenant;
if so add an org/tenant dimension with row-level scoping.
**Verify:** An operator can ack alerts but not manage users; an auditor is read-only;
(if built) tenant A cannot see tenant B's devices.

### Step 6.3 — 🟡 Password policy, account lifecycle, and session policy
**Why:** No visible password-complexity, expiry, or inactivity-timeout policy.
**What to do:** Enforce configurable password complexity, optional rotation, account
lockout, and idle-session timeout aligned to corporate policy.
**Verify:** Weak passwords are rejected; idle sessions expire per config.

### Step 6.4 — 🟢 Data governance: export, pagination limits, and retention proof
**Why:** Retention exists for metrics (good). Confirm API list endpoints paginate and
cap result sizes, and provide data export for compliance.
**What to do:** Enforce pagination + max-page-size on all list endpoints; add
audited data-export endpoints; document retention guarantees per data class.
**Verify:** Large list queries are bounded; export produces a complete, audited
artifact.

---

## Suggested execution order

1. **Tier 1** (security) — 1.1 → 1.2 → 1.3 → 1.4 → 1.5, then 1.6/1.7.
2. **Tier 3** CI first two steps (3.1, 3.2) in parallel — they protect everything after.
3. **Tier 2** reliability (2.1 → 2.3 → 2.2), interleaved with Tier 4 hardening (4.1, 4.2).
4. **Tier 5** observability once traffic patterns matter.
5. **Tier 6** enterprise features as customer requirements land (SSO usually first).

Each step is independently shippable and verifiable. Treat the 🔴 items as release
blockers for an "enterprise" label; 🟠 as fast-follows; 🟡/🟢 as backlog to prioritize
against customer demand.
