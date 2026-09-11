# observability/

Opt-in observability overlay (Step 5.2). Layer it on top of the base stack:

```bash
make observability-up      # or: docker-compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

- **Grafana** — http://localhost:3001 (login `admin` / `GF_SECURITY_ADMIN_PASSWORD`).
  Datasources and both dashboards auto-provision from `grafana/`.
- **Prometheus** — http://localhost:9090 (targets, `/alerts` for alert state).
- **Loki + Promtail** — container logs, queryable by the Step 5.1 JSON fields, e.g.
  `{container=~"snmp-.+"} | json | correlation_id="<id>"`.
- **node-exporter** — host CPU/mem/disk for the disk-usage alert.

## Layout

```
prometheus/prometheus.yml     scrape config
prometheus/alerts.yml         platform alert rules as code
grafana/provisioning/         datasources + dashboard provider
grafana/dashboards/           platform-health.json, device-overview.json
loki/loki-config.yml          single-binary Loki
promtail/promtail-config.yml  docker log discovery + JSON parsing
snmp-exporter/                see below
```

## Per-device metrics (token-gated)

The platform-health dashboard and every alert work with no extra setup. The
**device-overview** dashboard reads per-device metrics from the backend's
token-gated exporter (`/metrics/prometheus`). To enable that scrape job:

```bash
make observability-token   # writes PROMETHEUS_SCRAPE_TOKEN to prometheus/scrape_token (gitignored)
make observability-up
```

Without it, the `backend-device-metrics` Prometheus target simply shows as down.

## snmp-exporter/ (separate, not wired by default)

`snmp-exporter/` builds a [prom/snmp-exporter](https://github.com/prometheus/snmp_exporter)
image for polling devices **directly over SNMP from Prometheus** — an alternative
collection path, independent of this project's agent → manager → DuckDB pipeline.
It is not part of the default overlay (device targets are dynamic and managed in
Postgres). Kept here as a starting point if you ever want a Prometheus-native
SNMP path; add a service + a `snmp` scrape job with per-target relabeling to use it.
