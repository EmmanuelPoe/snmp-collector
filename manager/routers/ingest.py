import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from auth import require_api_key
from services.ingest import ChecksumError, DuplicateFileError, ingest_file

router = APIRouter(tags=["ingest"])

_VALID_TYPES = {"polls": "snmp_polls", "traps": "snmp_traps"}


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    x_file_id: str = Header(...),
    x_sha256: str = Header(...),
    _: str = Depends(require_api_key),
):
    parts = x_file_id.rsplit("_", 1)
    if len(parts) != 2 or parts[1] not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid file_id: {x_file_id}")

    table = _VALID_TYPES[parts[1]]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        rows = await ingest_file(x_file_id, x_sha256, tmp_path, table)
        return {"ok": True, "rows_ingested": rows}
    except ChecksumError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DuplicateFileError:
        return {"ok": True, "rows_ingested": 0, "duplicate": True}
    finally:
        tmp_path.unlink(missing_ok=True)
