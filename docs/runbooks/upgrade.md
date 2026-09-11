# Upgrade runbook — single-host production (Step 4.3)

Upgrade to a new release with a migration + restart. Expect brief API downtime
during the backend restart; ingest is absorbed by the agent disk queues (Step 2.3
backpressure) and re-uploaded after.

Shorthand for the prod invocation:

```bash
export COMPOSE="-f docker-compose.yml -f docker-compose.tls.yml -f docker-compose.prod.yml"
```

## 1. Back up first (always)

```bash
make backup            # Postgres dump + DuckDB snapshot → ./backups/<ts>
```

Note the timestamp — [rollback.md](rollback.md) needs it if the upgrade fails.

## 2. Fetch the new release

```bash
git fetch --tags && git checkout v1.x.y
# pin the new image tags in docker-compose.prod.yml, then pull:
docker-compose $COMPOSE pull
```

## 3. Apply schema migrations

The backend runs `alembic upgrade head` on start, but run it explicitly first so
a migration failure aborts *before* the new code serves traffic:

```bash
docker-compose $COMPOSE run --rm backend alembic upgrade head
```

Review the migration list in the release notes. If any migration is
**irreversible**, rollback requires a restore (see rollback.md) — decide your
risk tolerance here.

## 4. Recreate services (restart order)

```bash
docker-compose $COMPOSE up -d --remove-orphans
```

Compose recreates only changed services. Order matters when a migration changed
the contract: postgres → backend/manager → agent → nginx/frontend. Compose's
`depends_on` handles this; if you must do it by hand, start postgres first and
nginx last.

## 5. Verify

```bash
docker compose ps                          # all healthy
curl -sk https://<host>/api/health/ready   # ready
docker compose logs --since 5m backend | grep -iE 'error|traceback' | head
```

Spot-check: log in, confirm devices list, confirm a recent metric timestamp
(ingest resumed), confirm no alert-evaluator lateness warnings.

## 6. If it's wrong

Go to [rollback.md](rollback.md). If migrations were reversible, a tag rollback +
restart suffices; if not, restore the pre-upgrade backup from step 1.
