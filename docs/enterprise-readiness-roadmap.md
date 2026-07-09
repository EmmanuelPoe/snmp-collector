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
- [ ] **Step 1.3** — Rate-limit auth + login lockout *(plan Step 15)* ← **NEXT**
- [ ] **Step 1.4** — Token lifecycle: revocation, logout *(plan Step 16)*
- [ ] **Step 1.5** — Audit logging *(plan Step 17)*
- [ ] **Step 1.6** — CORS tightening + TLS/HSTS/security headers *(plan Step 18)*
- [ ] **Step 1.7** — Per-agent credentials (retire shared bearer for agents) *(plan Step 19)*
- [ ] **Step 3.1** — CI pipeline *(plan Step 20 — start in parallel with Tier 1)*
- [ ] **Step 3.2** — Lint / format / type-check gates *(plan Step 21)*
- [ ] **Step 3.3** — Dependency + image scanning, SBOM *(plan Step 22)*
- [ ] **Step 3.4** — Secret scanning *(plan Step 23)*
- [ ] **Step 3.5** — Frontend + E2E test coverage *(plan Step 24)*
- [ ] **Step 2.1** — Agent registry into Postgres *(plan Step 25)*
- [ ] **Step 2.2** — Harden silent failure paths *(plan Step 26)*
- [ ] **Step 2.3** — Liveness/readiness + ingest backpressure *(plan Step 27)*
- [ ] **Step 2.4** — Backups + tested restore (RPO/RTO) *(plan Step 28)*
- [ ] **Step 2.5** — Load-test harness at 1000 devices *(plan Step 29)*
- [ ] **Step 2.6** — Metrics-store decision gate (DuckDB vs TimescaleDB hot path) *(plan Step 30)*
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
- Backend tests (run locally — the backend image has no pytest): `cd backend && python -m pytest -q` → 156 passed.
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

### Step 1.3 — 🟠 Rate-limit authentication + login lockout *(plan Step 15)*
**Why:** No rate limiting exists anywhere (no slowapi in the backend, no `limit_req`
in `nginx/conf.d/default.conf`). `/auth/login` is brute-forceable, and the
MIB-walk endpoint can be used to hammer devices.
**What to do:** Per-IP rate limiting on `/auth/login`, password change, and
`/devices/{id}/walk`; per-account failed-login counter with temporary lockout,
persisted so it survives restarts (and feeds the audit trail in 1.5).
**Verify:** Automated test issues N rapid bad logins and receives `429` after the
threshold; the locked account rejects even a correct password until the lockout
expires.

### Step 1.4 — 🟠 Token lifecycle: revocation and logout *(plan Step 16)*
**Why:** JWTs are stateless with an 8h lifetime and no revocation
(`backend/auth.py:27-29`). A leaked token or deactivated user stays valid until
expiry; there is no logout invalidation and password change does not invalidate
old tokens.
**What to do:** Add a `token_version` on `User` (bumped on password change and
deactivation) plus a `jti` denylist for explicit logout, both checked during token
resolution. Add `POST /auth/logout`.
**Verify:** After logout or deactivation, the previously issued token is rejected;
password change invalidates old tokens.

### Step 1.5 — 🟠 Audit logging *(plan Step 17)*
**Why:** No audit trail exists (`grep -ri audit backend/` → nothing). Enterprises
require "who did what, when" for logins, device/credential changes, config edits,
and alert acknowledgements — and it is the backbone of the compliance track (6.4).
**What to do:** Add an append-only `audit_log` table (actor, action, target,
summary, source IP, timestamp) written from every mutating router, including
login success/failure. Expose an admin-only, filterable audit view. Credential
values are never written to audit rows.
**Verify:** Creating/editing/deleting a device and logging in each produce audit
rows with the acting user and source IP.

### Step 1.6 — 🟡 Tighten CORS and transport security *(plan Step 18)*
**Why:** CORS allows all methods and headers (`backend/main.py:83-89`); nginx
serves plain HTTP on :80 only (`nginx/conf.d/default.conf`), no TLS — and remote
agents talk to the manager on :8001 in cleartext, carrying SNMP credentials.
**What to do:** Restrict CORS methods/headers to what the SPA uses. Add TLS
termination (nginx 443 + HSTS, redirect 80→443) with a documented cert-management
path (Let's Encrypt / corporate CA), covering the manager's agent-facing port too.
Add security headers (CSP, X-Frame-Options, X-Content-Type-Options).
**Verify:** `curl -I https://…` shows HSTS + security headers; HTTP redirects to
HTTPS; disallowed CORS method is rejected.

### Step 1.7 — 🟡 Per-agent credentials — retire the shared bearer for agents *(plan Step 19)*
**Why:** One-time **enrollment** tokens already exist (`manager/routers/registration.py`
claim flow), but after enrollment every agent authenticates with the same static
`MANAGER_API_KEY` (`manager/auth.py:11`), which is also what the backend accepts for
internal calls (`backend/auth.py:81-86`). One leaked agent key compromises every hop,
and it never rotates.
**What to do:** Issue a per-agent secret at claim/registration (hash stored with the
registry record), authenticate all subsequent agent→manager calls with it, and make
revocation per-agent (deregister = revoke). Keep `MANAGER_API_KEY` only for
manager↔backend service calls, so a stolen agent credential cannot reach backend
internal endpoints.
**Verify:** Revoking one agent's credential blocks only that agent; an agent
credential presented to a backend internal endpoint is rejected.

---

## Tier 3 — CI/CD, quality gates & supply chain

Numbered Tier 3 but **starts in parallel with Tier 1** — CI protects every change
that follows.

### Step 3.1 — 🔴 Add a CI pipeline *(plan Step 20)*
**Why:** No `.github/workflows` exists. Nothing runs tests, lint, or builds on a PR.
**What to do:** Add CI (GitHub Actions) that on every PR: installs deps, runs the full
pytest suite (backend/manager/agent), builds all images, and runs the
`make simulation` end-to-end smoke test against the simulator. Block merge on failure.
**Verify:** A PR that breaks a test is red and unmergeable; a green PR shows all suites
passing.

### Step 3.2 — 🟠 Linting, formatting, and type checking as gates *(plan Step 21)*
**Why:** No `ruff`/`mypy`/`eslint`/`prettier` config present. Style and type
drift accumulate.
**What to do:** Add `ruff` (lint + format) + `mypy` for Python and `eslint` +
`prettier` for the React app, with configs checked in and a `pre-commit` config.
Wire them into CI.
**Verify:** CI fails on a lint/type violation; `pre-commit run --all-files` passes
locally.

### Step 3.3 — 🟠 Dependency and container vulnerability scanning *(plan Step 22)*
**Why:** Deps are pinned (good) but nothing scans them. No SBOM.
**What to do:** Enable Dependabot, run `pip-audit` + `npm audit` and image
scanning (Trivy) in CI, and generate an SBOM per image. Add a policy for
severity thresholds that block release.
**Verify:** A known-vulnerable pinned dep triggers a CI failure/alert; SBOM artifact is
produced per build.

### Step 3.4 — 🟡 Secret scanning *(plan Step 23)*
**Why:** `.env` is present in the working tree; risk of committed secrets.
**What to do:** Add `gitleaks` to CI and pre-commit; confirm `.env` and
`data/` are gitignored; scrub any historical secrets.
**Verify:** CI blocks a PR that introduces a secret-looking string.

### Step 3.5 — 🟡 Frontend and integration test coverage *(plan Step 24)*
**Why:** `frontend/src` has no tests; E2E is a manual `make simulation`.
**What to do:** Add React component/interaction tests for the critical
flows (login, device CRUD, alert feed) and a Playwright happy-path E2E in CI. Track
coverage with a floor that ratchets up.
**Verify:** CI reports frontend coverage; Playwright login→device→metrics flow passes
headless.

---

## Tier 2 — Reliability & scale (single host, 1000+ devices)

Reframed for the locked scope: the goal is **durability and a benchmarked
1000-device ceiling on one host**, not multi-node HA.

### Step 2.1 — 🟠 Move the agent registry into Postgres *(plan Step 25)*
**Why:** The manager persists the agent registry to a JSON file
(`manager/registry.py:81-86` — the write is atomic, but the state is in-memory,
lost on volume loss, not queryable, and invisible to backups). Per-agent
credentials (1.7) need a durable home too.
**What to do:** Move registry state (and agent credential hashes) into a Postgres
table; the manager becomes stateless on disk apart from DuckDB. Registry contents
then ride the Postgres backup path (2.4) for free.
**Verify:** Restarting the manager (or wiping its volume) preserves agent
registrations; registry rows appear in a Postgres backup.

### Step 2.2 — 🟠 Harden silent failure paths *(plan Step 26)*
**Why:** `manager/db.py:44-45` swallows all exceptions during schema migration;
the bootstrap block in `backend/main.py:63-64` swallows `OperationalError` (a dead
DB at startup proceeds silently); a corrupt registry file is silently discarded
(`manager/registry.py:96-97`). Silent failures hide corruption.
**What to do:** Narrow exception handling, log at WARNING/ERROR with context, and fail
loudly where a corrupt/locked DB should stop startup rather than continue.
**Verify:** Injecting a migration error surfaces a logged, actionable message instead
of silent continuation; backend refuses to start when Postgres is unreachable.

### Step 2.3 — 🟠 Liveness/readiness split + ingest backpressure *(plan Step 27)*
**Why:** Only postgres, backend, and manager have compose healthchecks; both
services expose a single `/health` that checks nothing. There is no backpressure
signal when ingest lags — agents keep uploading into a saturated write lock.
**What to do:** Add `/health/live` and `/health/ready` (ready checks Postgres/DuckDB).
Add healthchecks for every service in compose. Return `503` + `Retry-After` from
`/ingest` when the DuckDB write queue is saturated — the agent's existing disk
retry queue absorbs the deferral.
**Verify:** Killing Postgres flips readiness to unhealthy but liveness stays up;
saturated ingest returns a retryable status and the agent queues rather than drops.

### Step 2.4 — 🔴 Backups and tested restore (RPO/RTO) *(plan Step 28)*
**Why:** No backup/restore or PITR strategy exists for Postgres *or* the DuckDB
metrics file (`scripts/` has only the simulation runner). Data loss on a single
host is total.
**What to do:** Script and schedule `pg_dump` + a consistent DuckDB snapshot;
`make backup` / `make restore` targets; a tested restore runbook; stated RPO
(backup interval) and RTO targets.
**Verify:** A scheduled backup runs; a restore drill on a clean host reconstructs
devices, users, alerts, and metrics.

### Step 2.5 — 🔴 Load-test harness at the 1000-device target *(plan Step 29)*
**Why:** The scale target is a product commitment; today there are no numbers.
Known hot spots to measure: the single DuckDB write lock (`manager/db.py:8`), the
30s alert-evaluator loop's per-device fetches, and the Prometheus exporter's
N-sequential-calls-per-scrape pattern (flagged in Phase 2 of the implementation
plan).
**What to do:** Build a repeatable harness that simulates 1000 devices' ingest and
query load; publish benchmark numbers (ingest rows/s, `/ingest` p99, lock wait,
API query p99, evaluator loop duration) in a checked-in benchmark doc.
**Verify:** `make loadtest` (or equivalent) runs against a fresh stack and emits
the benchmark report.

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
