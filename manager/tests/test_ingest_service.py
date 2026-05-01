import hashlib
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_parquet(tmp_path: Path, table: str) -> Path:
    if table == "snmp_polls":
        data = pa.table({
            "agent_id": pa.array(["a1"]),
            "device_ip": pa.array(["1.2.3.4"]),
            "oid": pa.array(["1.3.6.1.2.1.1.3.0"]),
            "value": pa.array(["100"]),
            "collected_at": pa.array([datetime.now(timezone.utc)], type=pa.timestamp("us", tz="UTC")),
        })
    else:
        data = pa.table({
            "agent_id": pa.array(["a1"]),
            "device_ip": pa.array(["1.2.3.4"]),
            "trap_oid": pa.array(["1.3.6.1.6.3.1.1.5.3"]),
            "varbinds": pa.array(['{"ifIndex":"1"}']),
            "received_at": pa.array([datetime.now(timezone.utc)], type=pa.timestamp("us", tz="UTC")),
        })
    path = tmp_path / f"{table}.parquet"
    pq.write_table(data, path)
    return path


@pytest.mark.asyncio
async def test_ingest_polls_success(reset_db, tmp_path):
    from services.ingest import ingest_file
    path = _make_parquet(tmp_path, "snmp_polls")
    sha = _sha256(path)
    count = await ingest_file("agent-01_1000_polls", sha, path, "snmp_polls")
    assert count == 1

@pytest.mark.asyncio
async def test_ingest_traps_success(reset_db, tmp_path):
    from services.ingest import ingest_file
    path = _make_parquet(tmp_path, "snmp_traps")
    sha = _sha256(path)
    count = await ingest_file("agent-01_1000_traps", sha, path, "snmp_traps")
    assert count == 1

@pytest.mark.asyncio
async def test_wrong_checksum_raises_and_dead_letters(reset_db, tmp_path):
    from services.ingest import ingest_file, ChecksumError
    import config
    path = _make_parquet(tmp_path, "snmp_polls")
    with pytest.raises(ChecksumError):
        await ingest_file("agent-01_1001_polls", "deadbeef" * 8, path, "snmp_polls")
    dl_dir = Path(config.settings.dead_letter_path)
    assert (dl_dir / "agent-01_1001_polls.parquet").exists()
    assert (dl_dir / "agent-01_1001_polls.error.json").exists()

@pytest.mark.asyncio
async def test_duplicate_file_id_raises(reset_db, tmp_path):
    from services.ingest import ingest_file, DuplicateFileError
    path = _make_parquet(tmp_path, "snmp_polls")
    sha = _sha256(path)
    await ingest_file("agent-01_1002_polls", sha, path, "snmp_polls")
    path2 = _make_parquet(tmp_path, "snmp_polls")
    sha2 = _sha256(path2)
    with pytest.raises(DuplicateFileError):
        await ingest_file("agent-01_1002_polls", sha2, path2, "snmp_polls")

@pytest.mark.asyncio
async def test_tmp_file_deleted_after_success(reset_db, tmp_path):
    from services.ingest import ingest_file
    path = _make_parquet(tmp_path, "snmp_polls")
    sha = _sha256(path)
    await ingest_file("agent-01_1003_polls", sha, path, "snmp_polls")
    assert not path.exists()
