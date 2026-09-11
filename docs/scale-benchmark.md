# Scale benchmark — 1000-device target (Step 2.5 / plan Step 29)

The locked scale target is **1000+ devices on a single compose host**
(≈ 1000 devices × 30 interfaces × 10 OIDs / 60 s poll ≈ **5,000 rows/s**
sustained ingest). This document holds the test recipe and the published
numbers; Step 2.6 (metrics-store decision gate) reads its answer from here.

## Recipe

Fresh stack, then one command:

```bash
make reset && make migrate
SIM_ADMIN_PASSWORD=<admin pw> make loadtest
```

`make loadtest` runs:

1. **`scripts/loadtest/ingest_load.py`** — 4 synthetic agents uploading
   agent-sized Parquet batches (25 devices × 30 ifaces × 10 OIDs per batch)
   through the real `POST /ingest` for 120 s. Reports rows/s, upload p50/p99,
   503 deferrals (Step 2.3 backpressure), errors.
2. **`scripts/loadtest/query_load.py`** — 8 concurrent dashboard-like readers
   (alert counts, per-device rates, latest metrics) for 60 s + one
   Prometheus-exporter scrape. Reports query p50/p99, rps.
3. `docker stats` snapshot — CPU/RSS per container (feeds Step 4.2 limits).

Also capture from logs while the test runs:

```bash
docker compose logs backend | grep "alert evaluation"    # loop duration vs 30s cadence
ls -l data/db/metrics.db                                  # file growth rate
```

Repeat twice; results must agree within ~10% to publish.

## Published results

First run on the dev host (single-host compose, 8-core / 7.65 GiB Docker VM,
macOS). The ingest driver pushes as fast as the manager will accept, so
**ingest rows/s is the DuckDB write *ceiling*, not the steady-state load** — the
1000-device steady-state requirement is ≈ 5,000 rows/s (top of this doc).

| Date | Commit | Ingest rows/s | Upload p50/p99 ms | 503 deferrals | Query p50/p99 ms | Evaluator loop s | RSS (manager) | Verdict vs 5k rows/s |
|------|--------|---------------|-------------------|---------------|------------------|------------------|---------------|----------------------|
| 2026-08-11 | `aa913f9` | **510,020** (61.2M rows / 120 s) | 40.3 / 151.5 | **0** | 16.7 / 40.0 | 0.03–0.06 | 809 MiB | ✅ ~**100× headroom** |

Config: 1000 devices × 30 interfaces × 10 OIDs, 25-device batches, ingest
concurrency 4 (120 s); query concurrency 8 (60 s). Both drivers: **0 errors**.
DuckDB file grew to 643 MB over the run. `docker stats` at snapshot (post-load,
idle): manager 809 MiB RSS, backend 229 MiB, postgres 124 MiB, agent 72 MiB —
CPU < 1% each at rest; the ingest run kept all services healthy with no 503
backpressure and no evaluator lateness.

**Caveats / not yet measured:**
- Query load saw only **1 real device** (`devices_seen: 1`) — the backend query
  path resolves `device_id → ip` from Postgres, and the synthetic ingest fleet
  is not registered as Postgres devices. So query p50/p99 exercise the
  backend→manager→DuckDB hop against a 61M-row table but at low fan-out; a
  high-device-count query benchmark needs the fleet registered as real devices.
- `docker stats` is a post-run idle snapshot, not peak-under-load; peak CPU was
  not isolated. Manager RSS (809 MiB) reflects the DuckDB working set after
  ingesting 61M rows.
- Sustained-volume query latency as `snmp_polls` approaches ~10⁹ rows at 90-day
  retention is still open (see below).
- Second confirming run (the "within ~10%" rule) not yet done — single run so far.

## Known pressure points being measured

- The single DuckDB write lock (`manager/db.py`) — upload p99 + deferral count.
- Alert evaluator per-device fetches every 30 s — loop duration log line
  (WARNs when it exceeds its cadence).
- Prometheus exporter's sequential manager calls — scrape duration.
- DuckDB query latency as `snmp_polls` approaches ~10⁹ rows at 90-day
  retention — query p99 against a pre-filled database (re-run the recipe after
  letting ingest_load run long enough to build volume, or loop it).
