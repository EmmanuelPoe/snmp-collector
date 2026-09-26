# Rollback runbook — single-host production (Step 4.3)

Revert a bad upgrade. Two paths depending on whether the release's migrations are
reversible — the release notes must state this.

```bash
export COMPOSE="-f docker-compose.yml -f docker-compose.tls.yml -f docker-compose.prod.yml"
```

## Path A — reversible migrations (fast, no data loss)

1. Check out the previous tag and re-pin its image tags in
   `docker-compose.prod.yml`:
   ```bash
   git checkout v1.x.(y-1)
   docker-compose $COMPOSE pull
   ```
2. Downgrade the schema one revision at a time to the previous release's head
   (the value is in that release's notes):
   ```bash
   docker-compose $COMPOSE run --rm backend alembic downgrade <previous_head>
   ```
3. Recreate:
   ```bash
   docker-compose $COMPOSE up -d --remove-orphans
   ```

## Path B — irreversible migrations (restore from backup)

Use the backup taken in upgrade.md step 1 (or the latest good nightly).

1. Check out the previous tag + pin its images (as in Path A step 1).
2. Restore Postgres + DuckDB from the timestamped pair:
   ```bash
   make restore BACKUP=<ts>     # see docs/runbooks/restore.md
   ```
   Restore stops the writers, recreates the database inside TimescaleDB's
   pre/post-restore guard, swaps the DuckDB file, and restarts services.
3. **Data written between the backup and the rollback is lost** (bounded by your
   RPO — the backup interval). Announce accordingly.

## Verify (either path)

```bash
docker compose ps                          # all healthy
curl -sk https://<host>/api/health/ready   # ready
```

Log in, confirm the schema/app version, confirm devices and recent metrics.
Agents re-heal automatically if the restore predates their enrolment (Step 2.1
self-heal): they re-register on the manager's 404.
