from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture(autouse=True)
def _clear_fleet_cache():
    from routers import metrics

    metrics._fleet_cache.clear()


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
    _seed(
        get_db(),
        [
            ("ag1", "10.0.0.1", "Gi0/1", "ifInOctets", ".1", "1000000", t1),
            ("ag1", "10.0.0.1", "Gi0/1", "ifInOctets", ".1", "7000000", t2),
            ("ag1", "10.0.0.1", "Gi0/1", "ifOutOctets", ".2", "500000", t1),
            ("ag1", "10.0.0.1", "Gi0/1", "ifOutOctets", ".2", "2000000", t2),
            ("ag1", "10.0.0.1", "Gi0/1", "ifOperStatus", ".3", "1", t2),
            ("ag1", "10.0.0.1", "Gi0/1", "ifSpeed", ".4", "1000000000", t2),
        ],
    )

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
    _seed(
        get_db(),
        [
            ("ag1", "10.0.0.2", "Gi0/1", "ifInOctets", ".1", "4294967295", t1),
            ("ag1", "10.0.0.2", "Gi0/1", "ifInOctets", ".1", "1000", t2),
        ],
    )
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.2", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["interfaces"]["Gi0/1"]["current_in_bps"] == 0.0


def test_rates_ifhighspeed_preferred_over_ifspeed(client, auth_headers):
    from db import get_db

    t2 = datetime.now(timezone.utc)
    _seed(
        get_db(),
        [
            ("ag1", "10.0.0.3", "Gi0/1", "ifHighSpeed", ".1", "1000", t2),
            ("ag1", "10.0.0.3", "Gi0/1", "ifSpeed", ".2", "10000000", t2),
        ],
    )
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.3", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["interfaces"]["Gi0/1"]["speed_bps"] == 1_000_000_000


def test_rates_unknown_device_returns_empty(client, auth_headers):
    resp = client.get("/internal/metrics/rates?device_ip=99.99.99.99", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"interfaces": {}}


def test_rates_requires_auth(client):
    resp = client.get("/internal/metrics/rates?device_ip=10.0.0.1")
    assert resp.status_code == 401


def _fleet_fixture(conn, now):
    t1 = now - timedelta(seconds=60)
    rows = []
    # Gi0/1: 1 Gbps port moving 800 kbps in / 200 kbps out. 32-bit counters are
    # present too and must be ignored in favour of the HC pair.
    for dev, in_delta in (("10.1.0.1", 6_000_000), ("10.1.0.2", 600_000)):
        rows += [
            ("ag1", dev, "Gi0/1", "ifHCInOctets", ".1", "1000000", t1),
            ("ag1", dev, "Gi0/1", "ifHCInOctets", ".1", str(1_000_000 + in_delta), now),
            ("ag1", dev, "Gi0/1", "ifInOctets", ".1", "5", t1),
            ("ag1", dev, "Gi0/1", "ifInOctets", ".1", "999999999", now),
            ("ag1", dev, "Gi0/1", "ifHCOutOctets", ".2", "0", t1),
            ("ag1", dev, "Gi0/1", "ifHCOutOctets", ".2", "1500000", now),
            ("ag1", dev, "Gi0/1", "ifHighSpeed", ".3", "1000", now),
        ]
    _seed(conn, rows)


def test_fleet_traffic_totals_and_top_n(client, auth_headers):
    from db import get_db

    now = datetime.now(timezone.utc)
    _fleet_fixture(get_db(), now)

    resp = client.get("/internal/metrics/fleet-traffic?hours=1&top=1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["totals"]["devices"] == 2
    assert body["totals"]["interfaces"] == 2
    # (6.0M + 0.6M) bytes / 60 s * 8 = 880 kbps; the 32-bit counters are ignored.
    assert body["totals"]["in_bps"] == pytest.approx(880_000, rel=0.01)
    assert body["totals"]["out_bps"] == pytest.approx(400_000, rel=0.01)

    assert len(body["top_by_traffic"]) == 1
    top = body["top_by_traffic"][0]
    assert top["device_ip"] == "10.1.0.1"
    assert top["in_bps"] == pytest.approx(800_000, rel=0.01)
    assert top["utilization_pct"] == pytest.approx(0.08, rel=0.05)
    assert body["top_by_utilization"][0]["device_ip"] == "10.1.0.1"
    assert sum(p["in_bps"] for p in body["series"]) > 0


def test_fleet_traffic_empty_db(client, auth_headers):
    resp = client.get("/internal/metrics/fleet-traffic", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["series"] == []
    assert body["totals"]["devices"] == 0
    assert body["top_by_traffic"] == []


def test_fleet_traffic_requires_auth(client):
    assert client.get("/internal/metrics/fleet-traffic").status_code in (401, 403)


def test_fleet_traffic_drops_counter_resets_instead_of_reporting_zero(client, auth_headers):
    from db import get_db

    now = datetime.now(timezone.utc)
    t1 = now - timedelta(seconds=60)
    _seed(
        get_db(),
        [
            ("ag1", "10.2.0.1", "Gi0/1", "ifInOctets", ".1", "4294967295", t1),
            ("ag1", "10.2.0.1", "Gi0/1", "ifInOctets", ".1", "1000", now),  # 32-bit wrap
        ],
    )
    body = client.get("/internal/metrics/fleet-traffic", headers=auth_headers).json()
    assert body["totals"]["interfaces"] == 0
    assert body["series"] == []


def test_fleet_traffic_cache_is_bounded_and_quantised(client, auth_headers):
    from routers import metrics

    for hours in (1.001, 1.002, 1.003, 1.1):
        assert client.get(f"/internal/metrics/fleet-traffic?hours={hours}", headers=auth_headers).status_code == 200
    assert len(metrics._fleet_cache) == 1  # all quantise to the same key

    for top in range(1, 41):
        client.get(f"/internal/metrics/fleet-traffic?top={top}", headers=auth_headers)
    assert len(metrics._fleet_cache) <= metrics._FLEET_CACHE_MAX
