import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import config
import db
import metrics
from auth import require_agent_auth
from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from logging_json import get_logger
from services.ingest import ChecksumError, DuplicateFileError, ingest_file

router = APIRouter(tags=["ingest"])
logger = get_logger(__name__)


def _record_duckdb_size() -> None:
    try:
        metrics.duckdb_file_bytes.set(Path(config.settings.db_path).stat().st_size)
    except OSError:
        pass


_VALID_TYPES = {"polls": "snmp_polls", "traps": "snmp_traps"}


def reject_when_saturated():
    """Step 2.3 backpressure: runs as a route dependency, i.e. BEFORE the
    multipart body is parsed. Agents keep the file in their disk queue and
    retry after Retry-After — no data loss, just deferral."""
    if db.write_queue_depth() >= config.settings.ingest_max_queue:
        raise HTTPException(
            status_code=503,
            detail="Ingest queue is full — retry later",
            headers={"Retry-After": "30"},
        )


@router.post("/ingest", dependencies=[Depends(reject_when_saturated)])
async def ingest(
    request: Request,
    file: UploadFile = File(...),
    x_file_id: str = Header(...),
    x_sha256: str = Header(...),
    _: str = Depends(require_agent_auth),
):
    parts = x_file_id.rsplit("_", 1)
    if len(parts) != 2 or parts[1] not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid file_id: {x_file_id}")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_\-]{0,127}", x_file_id):
        raise HTTPException(status_code=400, detail=f"Invalid file_id format: {x_file_id}")

    table = _VALID_TYPES[parts[1]]

    MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload too large (max 100 MB)")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    started = time.monotonic()
    try:
        rows = await ingest_file(x_file_id, x_sha256, tmp_path, table)
        metrics.ingest_duration.labels(table=table).observe(time.monotonic() - started)
        metrics.ingest_rows.labels(table=table).inc(rows)
        metrics.ingest_last_success.set(datetime.now(timezone.utc).timestamp())
        metrics.ingest_queue_depth.set(db.write_queue_depth())
        _record_duckdb_size()
        logger.info("ingest accepted", extra={"file_id": x_file_id, "table": table, "rows": rows})
        return {"ok": True, "rows_ingested": rows}
    except ChecksumError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DuplicateFileError:
        logger.info("ingest duplicate ignored", extra={"file_id": x_file_id, "table": table})
        return {"ok": True, "rows_ingested": 0, "duplicate": True}
    finally:
        tmp_path.unlink(missing_ok=True)
