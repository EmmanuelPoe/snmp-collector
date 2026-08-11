# Metrics-store decision gate (Step 2.6 / plan Step 30)

**Decision (2026-08-11): keep DuckDB for the hot metrics path. Do not move to
TimescaleDB now.** TimescaleDB stays installed in the stack as the documented
escape hatch (see triggers below).

## Why this gate exists

Every manager write serializes through one global lock on a single DuckDB file
(`manager/db.py`), and the backend mounts that same file read-only. Whether that
architecture holds at the locked 1000-device target is an empirical question —
to be decided from measured numbers, not intuition. Those numbers now exist in
[scale-benchmark.md](scale-benchmark.md).

## Pre-stated pass/fail criteria

"Keep DuckDB" passes only if **all** of these hold at the 1000-device profile
(≈ 5,000 rows/s steady-state):

| # | Criterion | Threshold | Measured (`aa913f9`) | Result |
|---|-----------|-----------|----------------------|--------|
| 1 | Ingest ceiling vs steady-state | ≥ 2× (≥ 10k rows/s) | **510,020 rows/s** (~100×) | ✅ |
| 2 | Upload latency under load | p99 < 1 s | 152 ms | ✅ |
| 3 | Backpressure at steady state | 0 sustained 503s | 0 | ✅ |
| 4 | Dashboard query latency | p99 < 500 ms | 40 ms* | ✅* |
| 5 | Alert evaluator cadence | loop < 30 s | 0.03–0.06 s | ✅ |
| 6 | Ingest error rate | 0 | 0 | ✅ |

\* Query p99 was measured at low device fan-out (`devices_seen: 1`) — see the
open item below. It clears the bar, but not yet at 1000-device read fan-out.

**Verdict: 5.5 / 6 pass, one caveated.** DuckDB has ~100× ingest headroom over
the target and sub-second everything. Migrating the hot path to TimescaleDB now
would add operational complexity (dual stores, a second write path) to solve a
problem the numbers say we do not have.

## What "keep and tune" means

No migration. If/when volume grows, tune in this order (cheapest first):

1. **Batch/commit tuning** on the DuckDB write lock — already effective (0
   deferrals); revisit `INGEST_MAX_QUEUE` only if 503s appear.
2. **Retention** (`METRICS_RETENTION_DAYS`, default 90) keeps `snmp_polls`
   bounded; the open question is query latency as the table approaches ~10⁹ rows
   (see below).
3. **Partitioning / columnar batch** within DuckDB if query latency degrades.

## Escape hatch — when to reopen and move the hot path to TimescaleDB

TimescaleDB is already in the stack (the Postgres image ships the extension;
currently **0 hypertables**). Reopen this gate and migrate the hot metrics path
to a TimescaleDB hypertable if any of these fire:

- **Query p99 at realistic device fan-out** (1000 devices registered, dashboard
  readers hitting many `device_ip`s) exceeds ~500 ms and tuning (2)/(3) can't
  recover it. **This is the one unmeasured criterion — close it before declaring
  the gate fully done (see Open items).**
- Write-lock starvation appears (sustained 503 deferrals, upload p99 > 1 s) at
  higher ingest concurrency than the 4-agent test.
- The single-file/single-lock model blocks a required feature (e.g. concurrent
  compaction, multi-writer).

Migration path if triggered: create a `snmp_polls` hypertable in Postgres,
dual-write from the manager ingest path behind a flag, backfill from DuckDB
(columnar batch export → COPY), cut the backend metrics reader over to Postgres,
and keep DuckDB for columnar/ad-hoc batch. The backend already owns Postgres, so
the read path change is contained.

## Open items before this gate is 100% closed

- [ ] **High-fan-out query benchmark**: register the synthetic fleet as real
      Postgres devices and re-run `query_load.py` so `devices_seen ≈ 1000`.
      Confirms criterion 4 at scale. Until then the DuckDB decision is sound on
      ingest (the dominant risk) but provisional on read fan-out.
- [ ] **Second confirming ingest run** (the benchmark's "within ~10%" rule).
