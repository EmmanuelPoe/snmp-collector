"""Platform Prometheus metrics for the manager (Step 5.2).

Registered on the default prometheus_client registry so they ride the
Instrumentator `/metrics` endpoint Prometheus already scrapes. These describe the
ingest pipeline's health (the alerts in observability/prometheus/alerts.yml).
"""

from prometheus_client import Counter, Gauge, Histogram

ingest_rows = Counter(
    "snmp_ingest_rows_total",
    "Rows written to DuckDB via /ingest",
    ["table"],
)
ingest_duration = Histogram(
    "snmp_ingest_duration_seconds",
    "Time to validate and write one /ingest file",
    ["table"],
)
ingest_last_success = Gauge(
    "snmp_ingest_last_success_timestamp_seconds",
    "Unix timestamp of the last successful ingest (drives the freshness alert)",
)
ingest_queue_depth = Gauge(
    "snmp_ingest_queue_depth",
    "Coroutines holding or waiting on the DuckDB write lock",
)
write_lock_wait = Histogram(
    "snmp_write_lock_wait_seconds",
    "Time spent waiting to acquire the DuckDB write lock",
)
duckdb_file_bytes = Gauge(
    "snmp_duckdb_file_bytes",
    "Size of the DuckDB metrics file on disk",
)
agent_pending_uploads = Gauge(
    "snmp_agent_pending_uploads",
    "Uploads buffered on an agent, reported via heartbeat",
    ["agent_id"],
)
backup_age_seconds = Gauge(
    "snmp_backup_age_seconds",
    "Age of the newest backup artifact (drives the RPO alert)",
)
