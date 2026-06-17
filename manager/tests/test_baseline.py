import pytest
from datetime import datetime, timezone, timedelta


def _insert(conn, oid_name, value, ts):
    conn.execute(
        "INSERT INTO snmp_polls (agent_id, device_ip, interface_name, oid_name, oid, value, collected_at) "
        "VALUES ('a1','1.2.3.4','eth0',?,'1.3',?,?)",
        [oid_name, str(value), ts],
    )


def test_baseline_computes_p95_bps(client, auth_headers):
    import db
    conn = db.get_db()
    base = datetime.now(timezone.utc) - timedelta(minutes=30)
    # 7500 bytes / 60s = 1000 bps, constant across the series
    for i in range(11):
        _insert(conn, "ifHCInOctets", 7500 * i, base + timedelta(seconds=60 * i))

    resp = client.get("/internal/metrics/baseline",
                      params={"device_ip": "1.2.3.4", "days": 1}, headers=auth_headers)
    assert resp.status_code == 200
    eth0 = resp.json()["interfaces"]["eth0"]
    assert eth0["in_samples"] == 10
    assert abs(eth0["in_p95_bps"] - 1000) < 1.0


def test_baseline_excludes_counter_reset(client, auth_headers):
    import db
    conn = db.get_db()
    base = datetime.now(timezone.utc) - timedelta(minutes=30)
    # steady 1000 bps then a counter reset (value drops -> negative delta, excluded)
    _insert(conn, "ifHCInOctets", 0, base)
    _insert(conn, "ifHCInOctets", 7500, base + timedelta(seconds=60))
    _insert(conn, "ifHCInOctets", 15000, base + timedelta(seconds=120))
    _insert(conn, "ifHCInOctets", 10, base + timedelta(seconds=180))  # reset

    resp = client.get("/internal/metrics/baseline",
                      params={"device_ip": "1.2.3.4", "days": 1}, headers=auth_headers)
    eth0 = resp.json()["interfaces"]["eth0"]
    assert eth0["in_samples"] == 2  # 3rd delta (negative) excluded
    assert abs(eth0["in_p95_bps"] - 1000) < 1.0


def test_baseline_requires_auth(client):
    assert client.get("/internal/metrics/baseline", params={"device_ip": "x"}).status_code == 403
