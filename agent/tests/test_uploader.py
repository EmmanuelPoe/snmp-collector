import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone


def make_row(agent_id="ag-01", device_ip="10.0.0.1", iface="eth0", oid_name="ifInOctets"):
    return {
        "agent_id": agent_id,
        "device_ip": device_ip,
        "interface_name": iface,
        "oid_name": oid_name,
        "oid": "1.3.6.1.2.1.2.2.1.10.1",
        "value": "12345",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.mark.asyncio
async def test_flush_when_max_rows_reached(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_URL", "http://manager:8000")
    monkeypatch.setenv("MANAGER_API_KEY", "test-key")
    monkeypatch.setenv("UPLOAD_MAX_ROWS", "3")
    monkeypatch.setenv("UPLOAD_MAX_AGE_SECONDS", "9999")
    monkeypatch.setenv("QUEUE_PATH", str(tmp_path / "queue"))
    monkeypatch.setenv("AGENT_ID_PATH", str(tmp_path / "agent_id"))

    import config
    config.settings = config.Settings()

    from uploader import UploadBuffer
    buf = UploadBuffer(agent_id="ag-01")

    upload_called = []

    async def fake_upload(path, file_id):
        upload_called.append(file_id)

    buf._upload_file = fake_upload

    buf.add(make_row())
    buf.add(make_row())
    assert not upload_called
    await buf.add_and_maybe_flush(make_row())
    assert len(upload_called) == 1


@pytest.mark.asyncio
async def test_flush_when_max_age_reached(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_URL", "http://manager:8000")
    monkeypatch.setenv("MANAGER_API_KEY", "test-key")
    monkeypatch.setenv("UPLOAD_MAX_ROWS", "9999")
    monkeypatch.setenv("UPLOAD_MAX_AGE_SECONDS", "0")
    monkeypatch.setenv("QUEUE_PATH", str(tmp_path / "queue"))
    monkeypatch.setenv("AGENT_ID_PATH", str(tmp_path / "agent_id"))

    import config
    config.settings = config.Settings()

    from uploader import UploadBuffer
    buf = UploadBuffer(agent_id="ag-01")

    upload_called = []

    async def fake_upload(path, file_id):
        upload_called.append(file_id)

    buf._upload_file = fake_upload
    buf.add(make_row())
    await buf.add_and_maybe_flush(make_row())
    assert len(upload_called) == 1


@pytest.mark.asyncio
async def test_retry_queue_files_uploaded(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_URL", "http://manager:8000")
    monkeypatch.setenv("MANAGER_API_KEY", "test-key")
    monkeypatch.setenv("UPLOAD_MAX_ROWS", "500")
    monkeypatch.setenv("UPLOAD_MAX_AGE_SECONDS", "60")
    monkeypatch.setenv("QUEUE_PATH", str(tmp_path / "queue"))
    monkeypatch.setenv("AGENT_ID_PATH", str(tmp_path / "agent_id"))

    import config
    config.settings = config.Settings()

    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()

    import pyarrow as pa
    import pyarrow.parquet as pq
    rows = pa.table({
        "agent_id":       pa.array(["ag-01"]),
        "device_ip":      pa.array(["10.0.0.1"]),
        "interface_name": pa.array(["eth0"]),
        "oid_name":       pa.array(["ifInOctets"]),
        "oid":            pa.array(["1.3.6.1.2.1.2.2.1.10.1"]),
        "value":          pa.array(["12345"]),
        "collected_at":   pa.array([datetime.now(timezone.utc)], type=pa.timestamp("us", tz="UTC")),
    })
    file_id = "test-file_polls"
    pq.write_table(rows, queue_dir / f"{file_id}.parquet")

    from uploader import UploadBuffer
    buf = UploadBuffer(agent_id="ag-01")

    upload_called = []

    async def fake_upload(path, fid):
        upload_called.append(fid)

    buf._upload_file = fake_upload
    await buf.flush_retry_queue()
    assert len(upload_called) == 1
