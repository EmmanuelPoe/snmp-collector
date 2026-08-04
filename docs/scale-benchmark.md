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

> **Pending first run** — the harness landed 2026-07-19 with Docker
> unavailable on the dev host. Run the recipe above and fill this table;
> keep superseded rows for history.

| Date | Commit | Ingest rows/s | Upload p50/p99 ms | 503 deferrals | Query p50/p99 ms | Scrape ms | Evaluator loop s | Peak CPU / RSS (manager) | Verdict vs 5k rows/s |
|------|--------|---------------|-------------------|---------------|------------------|-----------|------------------|--------------------------|----------------------|
| —    | —      | —             | —                 | —             | —                | —         | —                | —                        | —                    |

## Known pressure points being measured

- The single DuckDB write lock (`manager/db.py`) — upload p99 + deferral count.
- Alert evaluator per-device fetches every 30 s — loop duration log line
  (WARNs when it exceeds its cadence).
- Prometheus exporter's sequential manager calls — scrape duration.
- DuckDB query latency as `snmp_polls` approaches ~10⁹ rows at 90-day
  retention — query p99 against a pre-filled database (re-run the recipe after
  letting ingest_load run long enough to build volume, or loop it).
