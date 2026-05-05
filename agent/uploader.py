import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

import config


class UploadBuffer:
    def __init__(self, agent_id: str):
        self._agent_id = agent_id
        self._rows: list[dict] = []
        self._first_row_at: float | None = None
        self._queue = Path(config.settings.queue_path)
        self._queue.mkdir(parents=True, exist_ok=True)

    def add(self, row: dict) -> None:
        if self._first_row_at is None:
            self._first_row_at = time.monotonic()
        self._rows.append(row)

    async def add_and_maybe_flush(self, row: dict) -> None:
        self.add(row)
        age = time.monotonic() - (self._first_row_at or time.monotonic())
        if (
            len(self._rows) >= config.settings.upload_max_rows
            or age >= config.settings.upload_max_age_seconds
        ):
            await self._flush()

    async def tick(self) -> None:
        if not self._rows:
            return
        age = time.monotonic() - (self._first_row_at or time.monotonic())
        if age >= config.settings.upload_max_age_seconds:
            await self._flush()

    def pending_count(self) -> int:
        return len(list(self._queue.glob("*.parquet")))

    async def _flush(self) -> None:
        if not self._rows:
            return
        rows, self._rows = self._rows, []
        self._first_row_at = None

        file_id = f"{uuid.uuid4().hex}_polls"
        path = self._queue / f"{file_id}.parquet"
        _write_parquet(rows, path)
        await self._upload_file(path, file_id)

    async def _upload_file(self, path: Path, file_id: str) -> None:
        sha256 = _sha256(path)
        try:
            async with httpx.AsyncClient() as client:
                with open(path, "rb") as f:
                    resp = await client.post(
                        f"{config.settings.manager_url}/ingest",
                        files={"file": (path.name, f, "application/octet-stream")},
                        headers={
                            "Authorization": f"Bearer {config.settings.manager_api_key}",
                            "X-File-ID": file_id,
                            "X-SHA256": sha256,
                        },
                        timeout=30.0,
                    )
                    resp.raise_for_status()
            path.unlink(missing_ok=True)
        except Exception:
            pass

    async def flush_retry_queue(self) -> None:
        now = time.time()
        for parquet_file in sorted(self._queue.glob("*.parquet")):
            age = now - parquet_file.stat().st_mtime
            if age > config.settings.retry_max_age_seconds:
                parquet_file.unlink(missing_ok=True)
                continue
            file_id = parquet_file.stem
            await self._upload_file(parquet_file, file_id)


def _write_parquet(rows: list[dict], path: Path) -> None:
    table = pa.table({
        "agent_id":       pa.array([r["agent_id"] for r in rows]),
        "device_ip":      pa.array([r["device_ip"] for r in rows]),
        "interface_name": pa.array([r["interface_name"] for r in rows]),
        "oid_name":       pa.array([r["oid_name"] for r in rows]),
        "oid":            pa.array([r["oid"] for r in rows]),
        "value":          pa.array([r["value"] for r in rows]),
        "collected_at":   pa.array(
            [datetime.fromisoformat(r["collected_at"]) for r in rows],
            type=pa.timestamp("us", tz="UTC"),
        ),
    })
    pq.write_table(table, path)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
