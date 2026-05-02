import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import pyarrow.parquet as pq
import config
from db import query, transactional_ingest

_VALID_TABLES = frozenset({"snmp_polls", "snmp_traps"})


class ChecksumError(Exception):
    pass


class DuplicateFileError(Exception):
    pass


async def ingest_file(
    file_id: str, claimed_sha256: str, tmp_path: Path, table: str
) -> int:
    if table not in _VALID_TABLES:
        raise ValueError(f"Unknown table: {table!r}")

    actual_sha256 = _sha256(tmp_path)
    if actual_sha256 != claimed_sha256.lower():
        _dead_letter(file_id, tmp_path, f"SHA256 mismatch: got {actual_sha256}")
        raise ChecksumError("SHA256 mismatch")

    if await query("SELECT file_id FROM ingest_log WHERE file_id = ?", [file_id]):
        tmp_path.unlink(missing_ok=True)
        raise DuplicateFileError(f"Already ingested: {file_id}")

    try:
        row_count = pq.read_table(str(tmp_path)).num_rows
        now = datetime.now(timezone.utc)
        await transactional_ingest(table, str(tmp_path), file_id, now, row_count)
        return row_count
    except Exception as exc:
        _dead_letter(file_id, tmp_path, str(exc))
        raise
    finally:
        tmp_path.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _dead_letter(file_id: str, src: Path, error: str) -> None:
    dl_dir = Path(config.settings.dead_letter_path)
    dl_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dl_dir / f"{file_id}.{ts}.parquet"
    if src.exists():
        shutil.move(str(src), dest)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (dl_dir / f"{file_id}.{ts}.error.json").write_text(
        json.dumps({
            "file_id": file_id,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, indent=2)
    )
