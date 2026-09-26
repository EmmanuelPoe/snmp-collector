"""Platform Prometheus metrics for the backend (Step 5.2).

Registered on the default prometheus_client registry so they ride the
Instrumentator `/internal/prometheus` endpoint Prometheus already scrapes.
"""

from prometheus_client import Gauge

alert_eval_last_duration = Gauge(
    "snmp_alert_eval_last_duration_seconds",
    "Duration of the most recent alert-evaluation run (must stay under its 30s cadence)",
)
