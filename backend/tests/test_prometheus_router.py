"""Tests for the Prometheus exporter endpoint."""
import config
from routers import prometheus
from models import Device


def _rates(**kw):
    base = {"status": "up", "speed_bps": 1000, "current_in_bps": 100.0,
            "current_out_bps": 50.0, "utilization_pct": 10.0, "error_count": 2}
    base.update(kw)
    return base


def test_requires_token_when_configured(client, db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "prometheus_scrape_token", "secret")
    assert client.get("/metrics/prometheus").status_code == 401
    assert client.get("/metrics/prometheus",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_disabled_when_token_empty(client, monkeypatch):
    monkeypatch.setattr(config.settings, "prometheus_scrape_token", "")
    assert client.get("/metrics/prometheus",
                      headers={"Authorization": "Bearer anything"}).status_code == 503


def test_renders_gauges(client, db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "prometheus_scrape_token", "secret")
    db_session.add(Device(name="r1", ip_address="10.0.0.1", enabled=True))
    db_session.commit()
    monkeypatch.setattr(prometheus, "_fetch_rates",
                        lambda ip: {"interfaces": {"eth0": _rates()}})

    resp = client.get("/metrics/prometheus", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200
    body = resp.text
    assert "# TYPE snmp_interface_in_bps gauge" in body
    assert 'snmp_interface_in_bps{device="r1",ip="10.0.0.1",interface="eth0"} 100.0' in body
    assert 'snmp_interface_up{device="r1",ip="10.0.0.1",interface="eth0"} 1' in body
    assert 'snmp_device_up{device="r1",ip="10.0.0.1"} 1' in body


def test_unreachable_device_marked_down(client, db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "prometheus_scrape_token", "secret")
    db_session.add(Device(name="r1", ip_address="10.0.0.1", enabled=True))
    db_session.commit()

    def boom(ip):
        raise RuntimeError("manager down")
    monkeypatch.setattr(prometheus, "_fetch_rates", boom)

    resp = client.get("/metrics/prometheus", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200
    assert 'snmp_device_up{device="r1",ip="10.0.0.1"} 0' in resp.text


def test_disabled_devices_excluded(client, db_session, monkeypatch):
    monkeypatch.setattr(config.settings, "prometheus_scrape_token", "secret")
    db_session.add(Device(name="off", ip_address="10.0.0.9", enabled=False))
    db_session.commit()
    monkeypatch.setattr(prometheus, "_fetch_rates", lambda ip: {"interfaces": {"eth0": _rates()}})
    resp = client.get("/metrics/prometheus", headers={"Authorization": "Bearer secret"})
    assert "10.0.0.9" not in resp.text


def test_label_escaping(monkeypatch):
    dev = Device(name='weird"name', ip_address="10.0.0.1", enabled=True)
    out = prometheus._render([(dev, {"interfaces": {"eth0": _rates()}})])
    assert 'device="weird\\"name"' in out
