# Implementation Plan

*Derived from [product-improvement-research.md](product-improvement-research.md). Verified against the codebase 2026-06-08. This is a build sequence, not a code listing — each step states what to change, where, the schema/migration impact, how to verify, and any decision that must be resolved before coding it.*

## Sequencing principle

Ordered by dependency → risk → payoff, not the research doc's priority numbers. Every step is independently shippable and independently verifiable. Phases 0 and 1 are the highest-value, lowest-risk block and should land first.

## Conventions for every step

- **Migrations**: all Postgres schema changes go through Alembic (`make migrate`). New revision numbered after `011_add_device_tags.py`.
- **Tests**: backend changes get a test in `backend/tests/` following existing router-test patterns; manager changes follow `manager/tests/`. `make test` runs the manager suite.
- **Frontend**: source changes require `docker-compose build frontend && docker-compose up -d frontend` (Nginx serves a pre-built bundle; `npm start` hot-reload is dev-only).
- **Commits**: one logical step per commit.

---

# Phase 0 — Bug fixes  ✅ DONE (commits 6664ec7, 05eefbf)

Smallest diffs, removes active alert noise. Ship these first.

**Resolved decisions:** Step 2 error-rate unit = **errors/sec**. Step 3 whitelist model = **required core + toggleable extras** (seed reconciled by migration 013).

**Discovered during Phase 0 (latent, pre-existing, NOT yet fixed):** the agent never collected `ifSpeed`/`ifHighSpeed`, so the rates endpoint reports `speed_bps = None` → `utilization_pct` is always null and **`bandwidth_threshold` alerts can never fire** (`_check_bandwidth_thresholds` skips interfaces with no speed). To make bandwidth alerting functional, add `ifHighSpeed` (1.3.6.1.2.1.31.1.1.1.15) and/or `ifSpeed` (1.3.6.1.2.1.2.2.1.5) as required OIDs in a follow-up migration. Out of Phase 0 scope; flagged for Phase 1.

## Step 1 — Virtual-interface denylist

**Problem (verified):** [`_check_interface_down`](../backend/alert_evaluator.py#L71-L94) fires `interface_down` for any interface whose `status == "down"`, including Linux virtual interfaces (`erspan0`, `gre0`, `sit0`, `tunl0`, …) that are always down.

**Change:**
- File: [backend/alert_evaluator.py](../backend/alert_evaluator.py)
- Add module-level `_VIRTUAL_IFACE_PREFIXES = ("erspan", "gre", "sit", "tunl", "ip6tnl", "bond", "lo")`.
- In `_check_interface_down`, exclude interfaces whose name starts with any prefix when building the `down` list.

**Migration:** none.

**Verify:** `make simulation`, then confirm the alert feed shows no `interface_down` for virtual interfaces. Add a unit test asserting a payload with `erspan0: down` produces no alert.

**Open decisions:** none. Prefix list is the agreed denylist from the research doc.

## Step 2 — Wire up error-rate alerting

**Problem (verified):** `AlertRule.error_rate` exists ([models.py:92](../backend/models.py#L92)) but no evaluator code path reads it.

**Change:**
- File: [backend/models.py](../backend/models.py) — add `error_rate = "error_rate"` to `AlertType`.
- Migration: new Alembic revision adding the enum value (Postgres `ALTER TYPE ... ADD VALUE`).
- File: [backend/alert_evaluator.py](../backend/alert_evaluator.py) — add `_check_error_rate(db, devices)`, call it from `run_evaluation`. Reuse the existing `_fetch_rates` payload, which already carries `error_count` per interface.

**Decision required before coding — error-rate semantics:** the rates payload exposes `error_count` (sum of `ifInErrors`/`ifOutErrors` deltas over the lookback window) but **no packet counts** — `ifInUcastPkts`/`ifOutUcastPkts` are not collected. Therefore "errors per packet" (the conventional definition) is **not computable today**. Options:
  - **(a) Errors over window** — compare `error_count` directly against `rule.error_rate`. Simplest, but window-length-dependent (`_RATES_LOOKBACK_HOURS = 0.1` → 360s).
  - **(b) Errors per second** — `error_count / window_seconds`. Window-independent; cleaner threshold semantics.
  - **(c) True error ratio** — requires first adding `ifInUcastPkts`/`ifOutUcastPkts` to the agent walk (depends on Step 3 being done) and surfacing packet deltas in the rates payload. Most correct, most work.
  - *Recommendation:* ship **(b)** now; revisit **(c)** after Step 3 if users want a true ratio. The `error_rate` field's unit label in the UI must match whichever is chosen.

**Verify:** unit test tripping the threshold against a synthetic rates payload; manual trip via simulator.

## Step 3 — Wire up the OID whitelist fully *(decision: build, not remove)*

**Problem (verified):** the agent hardcodes `_IF_OIDS` ([snmp.py:21-31](../agent/snmp.py#L21-L31)) and never reads `CollectionConfig`. The Config Manager OID UI is non-functional.

**Data path:** the OID whitelist is **global** (`CollectionConfig` table), not per-device. The agent receives device config from the manager, which proxies the backend's [`/internal/devices`](../backend/routers/internal.py#L12). The OID list rides that same fetch as a **separate top-level field**, not inside each per-device dict (`_to_device_config`).

**Change:**
1. **Backend** — extend the agent-facing device fetch to include enabled OIDs. Either add a sibling endpoint (e.g. `/internal/collection-config`) or change `/internal/devices` to return `{ "devices": [...], "oids": [{oid, oid_name}, ...] }`. Source: `CollectionConfig where enabled = true`.
2. **Manager** — forward the OID list through the registration/device-config response the agent consumes.
3. **Agent** — extend [agent/models.py](../agent/models.py) config object to carry the OID list; change `walk_device` ([snmp.py:46-82](../agent/snmp.py#L46-L82)) to iterate the supplied list instead of hardcoded `_IF_OIDS`. Keep `_IF_OIDS` as the default seed when the list is empty (so an empty config never silently halts collection).

**Hard constraint — `ifDescr` must always be walked.** `walk_device` builds the interface-name map from `ifDescr` (1.3.6.1.2.1.2.2.1.2) for *every* row ([snmp.py:51-61](../agent/snmp.py#L51-L61)). It must be walked unconditionally even if a user disables it in the UI, or all interface names break. Implementation: pin `ifDescr` internally (always walk it; exclude it from the user-toggleable set) **or** mark it non-disableable in the Config Manager UI.

**Migration:** none (CollectionConfig already exists). If `CollectionConfig` needs seeding with the default IF-MIB OIDs so the UI reflects current behavior, add a data migration.

**Verify:** disable an OID (e.g. `ifInErrors`) in Config Manager, `make simulation`, confirm that `oid_name` stops appearing in DuckDB `snmp_polls`; confirm interface names still resolve (ifDescr still walked).

**Note:** completing this unblocks the true error-ratio option (Step 2c) and is the foundation the MIB browser (Step 12) builds on.

---

# Phase 1 — Alerting workflow  ✅ DONE (commits 5b96fec, 6df4e39, 6a78d28, 465c103, df81209)

The research doc's "fastest path to a meaningfully better product." All contained backend + migration + frontend work.

**Resolved decisions:** Step 5 channels = Slack + generic webhook. Step 6 = suppress-new-only (open alerts still resolve). Step 7 `assigned_to` = FK to `users.id`, with `assigned_to_email`/`acknowledged_by_email` surfaced and a new editor/admin `GET /auth/users/assignable` endpoint for dropdowns.

**Also shipped (Phase 0.5, commit 5b96fec):** the `ifHighSpeed`/`ifSpeed` fix flagged at the end of Phase 0 — speed OIDs are now collected (migration 014), so `speed_bps` resolves and `bandwidth_threshold` alerts can finally fire.

**Deviation (Step 6):** built a dedicated **Maintenance page** (with a device/global scope selector) rather than a "Schedule Maintenance" button inside the device edit modal. Same capability, lower-risk than surgically editing the device modal. A per-device shortcut button could still be added later.

**Migrations added this phase:** 014 (speed OIDs), 015 (alert severity), 016 (notification_channels), 017 (maintenance_windows), 018 (alert ack/assign/note). Backend test count grew 87 → 109.

## Step 4 — Severity tiers on alerts

**Why first in this phase:** prerequisite for notification routing (Step 5) and alert filtering (Step 7).

**Change:**
- File: [backend/models.py](../backend/models.py) — add `AlertSeverity` enum (`critical`, `warning`, `info`) and `severity` column on `Alert`.
- Migration: add column with a default; backfill existing rows.
- File: [backend/alert_evaluator.py](../backend/alert_evaluator.py) — assign severity per `AlertType` at creation in `_create_alert` (e.g. `device_unreachable`/`agent_offline` → critical; `interface_down`/`bandwidth_threshold` → warning; `error_rate` → warning).
- Frontend: show severity in the alert feed and sidebar badge.

**Verify:** new alerts carry the expected severity; existing alerts backfilled.

## Step 5 — Outbound notifications (Slack / Teams / generic webhook)

**Research finding:** #1 most universal request across every tool's community.

**Change:**
- Migration + model: `notification_channels` table — `id`, `type` (`slack`/`teams`/`webhook`), `url`, `severity_filter`, `enabled`.
- New service `backend/services/notifications.py` — formats and POSTs the alert. **Fire-and-forget with a 3s timeout, wrapped so a dead/slow webhook never blocks or crashes the 30s evaluation loop.**
- Hook: call it from `_create_alert` in [backend/alert_evaluator.py](../backend/alert_evaluator.py) on **new** alert creation only (not on every re-evaluation), respecting each channel's `severity_filter` (depends on Step 4).
- Router: CRUD endpoints for channels (`backend/routers/`).
- Frontend: a Settings page to manage channels.

**Migration:** new table.

**Verify:** point a channel at a `webhook.site` URL, trip an alert, confirm the POST body and that a deliberately unreachable channel does not stall evaluation.

**Decision required:** payload format per channel type — Slack/Teams want their own JSON message card shape; generic webhook gets a raw alert JSON. Confirm whether Teams (now Power Automate workflows) is in scope or Slack + generic only for v1.

## Step 6 — Maintenance windows / suppression

**Research finding:** the canonical alert-fatigue fix.

**Change:**
- Migration + model: `maintenance_windows` table — `id`, `device_id` (nullable = global), `start_at`, `end_at`, `reason`.
- File: [backend/alert_evaluator.py](../backend/alert_evaluator.py) — at the start of `run_evaluation`, load active windows; skip suppressed devices in each `_check_*` (and skip global windows entirely). Suppression must prevent both **creation** and **notification** (Step 5).
- Router: CRUD endpoints.
- Frontend: "Schedule Maintenance" button in the device edit modal; an indicator on suppressed devices.

**Migration:** new table.

**Verify:** a window covering a device → no new alerts fire and no notifications send during it; alerts resume after `end_at`.

**Decision required:** during a window, do we (a) suppress new alerts only, or (b) also auto-resolve currently-open alerts for that device? Recommend (a) — suppress new, leave existing state untouched.

## Step 7 — Acknowledge / assign workflow

**Research finding:** open/resolved binary is insufficient for team use.

**Change:**
- Migration + model: add `acknowledged_by`, `acknowledged_at`, `assigned_to`, `note` to `Alert` ([models.py:72](../backend/models.py#L72)).
- Router: new PUT endpoints in [backend/routers/alerts.py](../backend/routers/alerts.py) for acknowledge / assign / note.
- Frontend: "Acknowledge" and "Assign" buttons + note field in the alert feed.

**Migration:** add columns.

**Verify:** ack persists across the 30s poll and survives the alert-message updates that `_check_interface_down` performs on open alerts (line 86); assignment shows in the feed.

**Decision required:** `assigned_to` — free-text string, or FK to the existing `User` table ([models.py:48](../backend/models.py#L48))? Recommend FK to `User` since auth/users already exist.

---

# Phase 2 — Integration & retention  ✅ DONE (commits 41e7e6f, 45c3a89, 222c02f)

**Resolved decisions:** Step 8 auth = dedicated `PROMETHEUS_SCRAPE_TOKEN` (empty disables the endpoint, 503). Step 9 = delete-only purge (physical file shrink deferred). Step 10 CSV = per-interface max/avg summary, range presets 7d/30d/90d.

**Endpoints added:** `GET /api/metrics/prometheus` (bearer-token exposition), `GET /api/metrics/export/csv/{device_id}` (CSV attachment), manager `GET /internal/metrics/summary`. Manager runs a weekly `_retention_loop` purging rows older than `METRICS_RETENTION_DAYS` (default 90). Backend tests 109 → 121; manager 68.

**Also flagged for later (not done):** the Prometheus exporter does N sequential manager calls per scrape (one per device) — fine for small fleets, worth batching into a single manager endpoint if device counts grow.

## Step 8 — Real Prometheus device exporter

**Correction to research doc:** the existing `/internal/prometheus` ([backend/main.py:84](../backend/main.py#L84)) is `prometheus-fastapi-instrumentator` — it exposes **HTTP request latency/counts for the FastAPI process, not device metrics.** This step is **net-new code**, not "exposing an existing endpoint."

**Change:**
- New authenticated endpoint (e.g. `/metrics/prometheus`) that reads DuckDB via the manager and emits per-device/per-interface gauges in Prometheus text format: current in/out bps, utilization %, error count, interface status (1/0). Reuses the rates query logic already in [manager/routers/metrics.py](../manager/routers/metrics.py).
- Labels: `device`, `interface`, `ip`.

**Migration:** none.

**Verify:** `curl` the endpoint with auth → valid Prometheus exposition format; scrape from a local Prometheus and confirm gauges appear.

**Decision required:** auth model for an external scraper — Prometheus scrape configs support bearer tokens; confirm the token strategy (reuse `MANAGER_API_KEY` or a dedicated scrape token).

## Step 9 — DuckDB retention + compaction

**Change:**
- **Lives in the manager** (manager owns DuckDB read-write; backend mounts read-only — do not write from backend).
- New weekly background task in the manager: `DELETE FROM snmp_polls WHERE collected_at < now() - INTERVAL` and `VACUUM` (apply to `snmp_traps` too).
- Config: `METRICS_RETENTION_DAYS` (default 90) in [manager/config.py](../manager/config.py) + `.env.example`.

**Migration:** none.

**Verify:** seed old rows, run the task manually, confirm deletion and file-size reclamation.

**Decision required:** DuckDB `VACUUM` does not shrink the file the way Postgres does; confirm whether a checkpoint/compaction or periodic file rewrite is needed to actually reclaim disk, or whether delete-only is acceptable for v1.

## Step 10 — CSV export

**Change:**
- Backend endpoint generating per-interface max/avg bandwidth utilization over a user-specified date range (reads DuckDB through the manager).
- Frontend "Export" button on the device metrics view.

**Migration:** none.

**Verify:** export a known range, open the CSV, spot-check max/avg against the trend chart.

**Decision required:** CSV granularity — raw poll rows, or pre-aggregated per-interface summary? Research doc specifies summary (max/avg per interface); confirm.

---

# Phase 3 — Differentiators (larger scope, after Phase 0–1 prove out)

## Step 11 — Dynamic baselines (anomaly detection)

7-day rolling p95 per interface per metric via a single DuckDB query; alert when current value `> rolling_p95 * 1.5`. New `AlertType`. Requires enough history to be meaningful — ship after retention (Step 9) is in place so the window is bounded. Decision: per-metric multiplier and minimum-history guard before the baseline is trusted.

## Step 12 — MIB browser / OID explorer

"Walk Device" UI action → backend → agent performs an on-demand SNMP walk → returns the OID tree for browsing; clicking an OID adds it to `CollectionConfig`. Builds directly on Step 3's OID wire-up. Requires a new agent command channel (the agent currently only polls + uploads; it has no request/response path for ad-hoc walks) — that's the main new surface.

## Step 13 — Topology map + dependency suppression

Largest scope. LLDP MIB collection in the agent (`lldpRemTable`), topology graph stored in Postgres, React graph viz (Cytoscape.js or D3), and parent-down → child-suppression in the evaluator. Highest differentiator per the research doc; do last.

## Step 14 — Trap correlation / enrichment

Cross-reference incoming traps (currently stored as raw JSON varbinds in DuckDB `snmp_traps`) with polled interface status — e.g. a `linkDown` trap on `eth0` annotates or auto-creates the corresponding `interface_down` alert. Deduplicate within a time window; enrich with device context.

---

# What we are explicitly not building yet

Per the research doc: multi-tenancy, full HA/clustering (DuckDB write-once model limits it), mobile app (responsive web suffices), AI root-cause analysis (insufficient labeled data volume).

---

# Recommended first block

Phase 0 (Steps 1–3) + Phase 1 (Steps 4–7). Resolve these decisions before coding the affected step:
- **Step 2:** error-rate semantics — recommend errors/sec (option b).
- **Step 5:** Slack + generic webhook only for v1, or include Teams?
- **Step 6:** suppress-new-only vs. also auto-resolve.
- **Step 7:** `assigned_to` as FK to `User` (recommended) vs. free text.
