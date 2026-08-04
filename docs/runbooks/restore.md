# Backup & restore runbook

**RPO (recovery point objective): the backup interval — default 24 h.**
**RTO (recovery time objective): ≤ 30 minutes** on a prepared host (the drill
below is ~10 minutes of hands-on time; the rest is margin for host setup).

## What a backup contains

`make backup` (→ `scripts/backup.sh`) produces a timestamped pair in
`./backups/`:

| Artifact | Contents |
|---|---|
| `postgres-<ts>.dump` | Everything relational: users, devices (encrypted SNMP credentials), collection configs, alerts + rules, notification channels, maintenance windows, topology, audit log, **agent registry incl. credential hashes** |
| `metrics-<ts>.db` | DuckDB time-series (snmp_polls, snmp_traps, ingest_log), CHECKPOINTed and copied under the manager's write lock — consistent even while ingest is running |

Not backed up on purpose: agent disk queues (in-flight buffers — agents
re-poll), enrollment slots (TTL'd one-time tokens), `.env` (secrets — manage
via your secret store; **a restore is useless without the matching
`ENCRYPTION_KEY`/`JWT_SECRET`**, so store `.env` wherever you store secrets).

## Scheduling (single-host posture: host cron)

```cron
# Daily at 02:15, keep newest 14 of each artifact (BACKUP_KEEP to change)
15 2 * * * cd /path/to/snmp-collector && ./scripts/backup.sh >> backups/backup.log 2>&1
```

Ship `./backups/` off-host (rsync/rclone target of your choice) — a backup on
the same disk protects against operator error, not host loss.

## Restore drill (also the real procedure)

On the same host, or a clean checkout on a new host:

```bash
# New host only: clone, copy .env from your secret store, make build
ls backups/                       # pick a timestamp pair
make restore BACKUP=20260719-021500
```

`scripts/restore.sh` stops the writers (backend/manager/agent), runs
`pg_restore --clean --if-exists`, copies the DuckDB snapshot over
`data/db/metrics.db`, and restarts the services.

**Verify after restore:**

1. `make status` — all services healthy.
2. Log in with a pre-backup account; devices, alerts, and audit history match
   the backup time.
3. Metrics charts show data up to the backup timestamp — and **not** after
   (that gap proves the restore actually swapped the data; new polls fill it
   forward within a poll cycle).
4. Agents reconnect without re-enrollment (registry + credential hashes rode
   the Postgres dump).

## Quarterly drill

Run the restore on a scratch checkout each quarter and record the elapsed
time in the compliance evidence pack (Step 6.4). If it exceeds the 30-minute
RTO, treat it as an incident and fix the runbook or tooling.
