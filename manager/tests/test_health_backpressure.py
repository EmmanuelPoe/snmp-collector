"""Liveness/readiness + ingest backpressure (Step 2.3 / plan Step 27)."""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_live_and_health_alias(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health").status_code == 200


def test_ready_reports_duckdb_and_registry(client, reset_db):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["duckdb"] == "ok"
    assert "write_queue" in body


def test_ingest_sheds_load_when_saturated(client, auth_headers, sample_polls_parquet, monkeypatch, reset_db):
    """With the queue over the limit, /ingest 503s before touching the body and
    sets Retry-After; below the limit the same upload succeeds."""
    import config

    monkeypatch.setattr(config.settings, "ingest_max_queue", 0)  # always saturated
    sha = hashlib.sha256(sample_polls_parquet.read_bytes()).hexdigest()

    def _post():
        with open(sample_polls_parquet, "rb") as f:
            return client.post(
                "/ingest",
                files={"file": ("polls.parquet", f, "application/octet-stream")},
                headers={**auth_headers, "X-File-ID": "bp1_polls", "X-SHA256": sha},
            )

    resp = _post()
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "30"

    monkeypatch.setattr(config.settings, "ingest_max_queue", 8)
    resp = _post()
    assert resp.status_code == 200
    assert resp.json()["rows_ingested"] == 5


def test_backup_endpoint_snapshots_duckdb(client, auth_headers, monkeypatch, tmp_path, reset_db):
    """Step 2.4: CHECKPOINT+copy under the write lock produces a usable snapshot."""
    import config

    monkeypatch.setattr(config.settings, "backup_dir", str(tmp_path / "backups"))
    resp = client.post("/internal/backup", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["bytes"] > 0
    snapshot = Path(body["path"])
    assert snapshot.exists()

    # The snapshot is a valid DuckDB database with the expected tables.
    import duckdb

    conn = duckdb.connect(str(snapshot), read_only=True)
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    conn.close()
    assert {"snmp_polls", "snmp_traps", "ingest_log"} <= tables


def test_backup_endpoint_requires_shared_key(client, reset_db):
    assert client.post("/internal/backup", headers={"Authorization": "Bearer wrong"}).status_code == 401
