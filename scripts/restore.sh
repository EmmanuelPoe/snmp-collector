#!/bin/bash
# Restore (Step 2.4 / plan Step 28): bring back Postgres + DuckDB from a
# timestamped backup pair produced by scripts/backup.sh.
#
#   ./scripts/restore.sh <timestamp>     # e.g. 20260719-021500
#   make restore BACKUP=<timestamp>
#
# Full drill and RPO/RTO statement: docs/runbooks/restore.md
set -euo pipefail

cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TS="${1:?usage: restore.sh <timestamp> (e.g. 20260719-021500)}"

PG_DUMP="$BACKUP_DIR/postgres-$TS.dump"
DUCK_DB="$BACKUP_DIR/metrics-$TS.db"
[ -f "$PG_DUMP" ] || { echo "✗ $PG_DUMP not found" >&2; exit 1; }
[ -f "$DUCK_DB" ] || { echo "✗ $DUCK_DB not found" >&2; exit 1; }

# shellcheck disable=SC1091
[ -f .env ] && set -a && source .env && set +a

echo "→ Stopping writers (backend, manager, agent)…"
docker-compose stop backend manager agent

echo "→ Restoring Postgres from $PG_DUMP…"
docker-compose exec -T postgres pg_restore --clean --if-exists \
    -U "${POSTGRES_USER:?}" -d "${POSTGRES_DB:?}" < "$PG_DUMP"

echo "→ Restoring DuckDB from $DUCK_DB…"
cp "$DUCK_DB" data/db/metrics.db

echo "→ Restarting services…"
docker-compose start manager backend agent

echo "✓ Restore complete from $TS. Verify: make status, then spot-check devices/metrics in the UI."
