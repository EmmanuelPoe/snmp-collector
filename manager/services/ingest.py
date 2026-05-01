import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import config
from db import execute, query, ingest_parquet


class ChecksumError(Exception):
    pass


class DuplicateFileError(Exception):
    pass


async def ingest_file(
    file_id: str, claimed_sha256: str, tmp_path: Path, table: str
) -> int:
    actual_sha256 = _sha256(tmp_path)
    if actual_sha256 != claimed_sha256.lower():
        _dead_letter(file_id, tmp_path, f"SHA256 mismatch: got {actual_sha256}")
        raise ChecksumError("SHA256 mismatch")

    if query("SELECT file_id FROM ingest_log WHERE file_id = ?", [file_id]):
        tmp_path.unlink(missing_ok=True)
        raise DuplicateFileError(f"Already ingested: {file_id}")

    try:
        row_count = await ingest_parquet(table, str(tmp_path))
        await execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?)",
            [file_id, datetime.now(timezone.utc), row_count],
        )
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
    dest = dl_dir / f"{file_id}.parquet"
    if src.exists():
        shutil.move(str(src), dest)
    (dl_dir / f"{file_id}.error.json").write_text(
        json.dumps({
            "file_id": file_id,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, indent=2)
    )
