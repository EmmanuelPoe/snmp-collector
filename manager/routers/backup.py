"""Backup trigger (Step 2.4 / plan Step 28). Operator/backend-facing —
shared-key auth, never agent credentials."""

import config
import db
from auth import require_api_key
from fastapi import APIRouter, Depends

router = APIRouter(tags=["backup"])


@router.post("/internal/backup")
async def backup(_: str = Depends(require_api_key)):
    """CHECKPOINT + copy the DuckDB file into the backup dir, serialized with
    ingest by the write lock. scripts/backup.sh drives this alongside pg_dump."""
    return await db.backup_database(config.settings.backup_dir)
