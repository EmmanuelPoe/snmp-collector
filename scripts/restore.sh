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

echo "→ Restoring Postgres from ${PG_DUMP} (drop/recreate ${POSTGRES_DB:?})…"
# The Postgres image ships the TimescaleDB extension, which registers catalog
# data (sequences in _timescaledb_catalog/_config) into the dump. A plain
# `pg_restore --clean` cannot reconcile that and drops the extension mid-restore,
# so we follow TimescaleDB's documented procedure: recreate the database fresh,
# then restore inside a pre/post-restore guard. This holds whether or not any
# hypertables exist today (roadmap 2.6 keeps TimescaleDB as the hot-path option).
docker-compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:?}" -d postgres <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "${POSTGRES_DB}";
CREATE DATABASE "${POSTGRES_DB}" OWNER "${POSTGRES_USER}";
SQL
docker-compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" \
    -c "SELECT timescaledb_pre_restore();"
# post_restore MUST run even if pg_restore reports non-fatal errors, otherwise the
# extension is left stuck in restore mode — so capture its status without aborting.
set +e
docker-compose exec -T postgres pg_restore --no-owner \
    -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" < "$PG_DUMP"
restore_rc=$?
set -e
docker-compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    -c "SELECT timescaledb_post_restore();"
[ "$restore_rc" -eq 0 ] || echo "⚠ pg_restore exited ${restore_rc} (see output above) — review before trusting this restore."

echo "→ Restoring DuckDB from ${DUCK_DB}…"
cp "$DUCK_DB" data/db/metrics.db

echo "→ Restarting services…"
docker-compose start manager backend agent

echo "✓ Restore complete from $TS. Verify: make status, then spot-check devices/metrics in the UI."
