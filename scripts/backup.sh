#!/bin/bash
# Backup (Step 2.4 / plan Step 28): Postgres pg_dump + DuckDB snapshot.
#
#   ./scripts/backup.sh            # or: make backup
#
# Artifacts land in BACKUP_DIR (default ./backups):
#   postgres-<ts>.dump   custom-format pg_dump (devices, users, alerts, audit,
#                        agent registry — everything relational)
#   metrics-<ts>.db      DuckDB snapshot, CHECKPOINTed + copied under the
#                        manager's write lock (safe while ingest is running)
#
# Retention: keeps the newest BACKUP_KEEP (default 14) of each artifact.
# Schedule via host cron (single-host posture), e.g. daily at 02:15:
#   15 2 * * * cd /path/to/snmp-collector && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
MANAGER_URL="${MANAGER_URL:-http://localhost:8001}"
TS=$(date -u +%Y%m%d-%H%M%S)

# shellcheck disable=SC1091
[ -f .env ] && set -a && source .env && set +a

mkdir -p "$BACKUP_DIR"

echo "→ Postgres dump…"
docker-compose exec -T postgres pg_dump -Fc -U "${POSTGRES_USER:?set in .env}" -d "${POSTGRES_DB:?set in .env}" \
    > "$BACKUP_DIR/postgres-$TS.dump"
echo "  $BACKUP_DIR/postgres-$TS.dump ($(wc -c < "$BACKUP_DIR/postgres-$TS.dump" | tr -d ' ') bytes)"

echo "→ DuckDB snapshot (via manager, serialized with ingest)…"
RESP=$(curl -fsS -X POST -H "Authorization: Bearer ${MANAGER_API_KEY:?set in .env}" "$MANAGER_URL/internal/backup")
echo "  $RESP"

echo "→ Retention (keep newest $BACKUP_KEEP of each)…"
for pattern in 'postgres-*.dump' 'metrics-*.db'; do
    ls -1t $BACKUP_DIR/$pattern 2>/dev/null | tail -n +$((BACKUP_KEEP + 1)) | xargs -I{} rm -v {} || true
done

echo "✓ Backup complete: $TS"
