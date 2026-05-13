import pytest
from datetime import datetime, timezone, timedelta


def _seed(conn, rows):
    conn.executemany(
        "INSERT INTO snmp_polls "
        "(agent_id, device_ip, interface_name, oid_name, oid, value, collected_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def test_rates_basic_delta(client, auth_headers):
    from db import get_db
    t2 = datetime.now(timezone.utc)
    t1 = t2 - timedelta(seconds=60)
    _seed(get_db(), [
        ("ag1", "10.0.0.1", "Gi0/1", "ifInOctets",    ".1", "1000000",     t1),
        ("ag1", "10.0.0.1", "Gi0/1", "ifInOctets",    ".1", "7000000",     t2),
        ("ag1", "10.0.0.1", "Gi0/1", "ifOutOctets",   ".2", "500000",      t1),
        ("ag1", "10.0.0.1", "Gi0/1", "ifOutOctets",   ".2", "2000000",     t2),
        ("ag1", "10.0.0.1", "Gi0/1", "ifOperStatus",  ".3", "1",           t2),
        ("ag1", "10.0.0.1", "Gi0/1", "ifSpeed",       ".4", "1000000000",  t2),
    ])

    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.1", headers=auth_headers)
    assert resp.status_code == 200
    iface = resp.json()["interfaces"]["Gi0/1"]

    assert iface["current_in_bps"] == pytest.approx(800000, rel=0.01)
    assert iface["current_out_bps"] == pytest.approx(200000, rel=0.01)
    assert iface["status"] == "up"
    assert iface["speed_bps"] == 1_000_000_000
    assert iface["utilization_pct"] == pytest.approx(0.08, rel=0.05)
    assert len(iface["sparkline"]) == 1
    assert iface["sparkline"][0]["in_bps"] == pytest.approx(800000, rel=0.01)


def test_rates_counter_wrap_returns_zero(client, auth_headers):
    from db import get_db
    t2 = datetime.now(timezone.utc)
    t1 = t2 - timedelta(seconds=60)
    _seed(get_db(), [
        ("ag1", "10.0.0.2", "Gi0/1", "ifInOctets", ".1", "4294967295", t1),
        ("ag1", "10.0.0.2", "Gi0/1", "ifInOctets", ".1", "1000",       t2),
    ])
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.2", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["interfaces"]["Gi0/1"]["current_in_bps"] == 0.0


def test_rates_ifhighspeed_preferred_over_ifspeed(client, auth_headers):
    from db import get_db
    t2 = datetime.now(timezone.utc)
    _seed(get_db(), [
        ("ag1", "10.0.0.3", "Gi0/1", "ifHighSpeed", ".1", "1000", t2),
        ("ag1", "10.0.0.3", "Gi0/1", "ifSpeed",     ".2", "10000000", t2),
    ])
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.3", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["interfaces"]["Gi0/1"]["speed_bps"] == 1_000_000_000


def test_rates_unknown_device_returns_empty(client, auth_headers):
    resp = client.get("/internal/metrics/rates?device_ip=99.99.99.99", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"interfaces": {}}


def test_rates_requires_auth(client):
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.1")
    assert resp.status_code == 403
