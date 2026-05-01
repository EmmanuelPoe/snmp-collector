import hashlib
import pytest
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_ingest_polls_success(client, auth_headers, sample_polls_parquet):
    sha = _sha256(sample_polls_parquet)
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "agent-01_1000_polls", "x-sha256": sha},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 5

def test_ingest_traps_success(client, auth_headers, sample_traps_parquet):
    sha = _sha256(sample_traps_parquet)
    with open(sample_traps_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "agent-01_1000_traps", "x-sha256": sha},
            files={"file": ("traps.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 3

def test_ingest_wrong_checksum_returns_400(client, auth_headers, sample_polls_parquet):
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "agent-01_1001_polls", "x-sha256": "bad" * 20},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 400

def test_ingest_duplicate_is_idempotent(client, auth_headers, sample_polls_parquet):
    sha = _sha256(sample_polls_parquet)
    for _ in range(2):
        with open(sample_polls_parquet, "rb") as f:
            resp = client.post(
                "/ingest",
                headers={**auth_headers, "x-file-id": "agent-01_1002_polls", "x-sha256": sha},
                files={"file": ("polls.parquet", f, "application/octet-stream")},
            )
        assert resp.status_code == 200
    # Only 5 rows total, not 10
    from db import query
    count = query("SELECT COUNT(*) FROM snmp_polls")[0][0]
    assert count == 5

def test_ingest_invalid_file_id_format_returns_400(client, auth_headers, sample_polls_parquet):
    sha = _sha256(sample_polls_parquet)
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={**auth_headers, "x-file-id": "badformat", "x-sha256": sha},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 400

def test_ingest_no_auth_returns_403(client, sample_polls_parquet):
    sha = _sha256(sample_polls_parquet)
    with open(sample_polls_parquet, "rb") as f:
        resp = client.post(
            "/ingest",
            headers={"x-file-id": "agent-01_1003_polls", "x-sha256": sha},
            files={"file": ("polls.parquet", f, "application/octet-stream")},
        )
    assert resp.status_code == 403
