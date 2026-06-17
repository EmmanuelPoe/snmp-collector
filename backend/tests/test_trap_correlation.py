"""Tests for SNMP trap correlation (synthetic traps — no live trap source)."""
import json
from datetime import datetime, timezone, timedelta

import pytest

import alert_evaluator
from models import Alert, AlertStatus, AlertType, Device

_LINK_DOWN = "1.3.6.1.6.3.1.1.5.3"
_LINK_UP = "1.3.6.1.6.3.1.1.5.4"


@pytest.fixture(autouse=True)
def _reset_watermark():
    alert_evaluator._last_trap_ts = None
    yield
    alert_evaluator._last_trap_ts = None


def _trap(device_ip, trap_type, ifindex=2, received_at=None, when=None):
    vb = {"1.3.6.1.6.3.1.1.4.1.0": trap_type}
    if ifindex is not None:
        vb[f"1.3.6.1.2.1.2.2.1.1.{ifindex}"] = str(ifindex)
    ts = received_at or (when or datetime.now(timezone.utc)).isoformat()
    return {"agent_id": "a1", "device_ip": device_ip, "trap_oid": "1.3.6.1.2.1.1.3.0",
            "varbinds": json.dumps(vb), "received_at": ts}


def _open_iface_down(db, device_id=None):
    q = db.query(Alert).filter(Alert.alert_type == AlertType.interface_down,
                               Alert.status == AlertStatus.open)
    if device_id is not None:
        q = q.filter(Alert.device_id == device_id)
    return q.all()


def _device(db, ip="10.0.0.1", name="r1"):
    d = Device(name=name, ip_address=ip, enabled=True)
    db.add(d)
    db.commit()
    return d


def test_first_run_skips_history(db_session, monkeypatch):
    d = _device(db_session)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps",
                        lambda hours=0.25: [_trap(d.ip_address, _LINK_DOWN)])
    # _last_trap_ts is None -> first pass adopts watermark, creates nothing
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    assert _open_iface_down(db_session) == []
    assert alert_evaluator._last_trap_ts is not None


def test_linkdown_autocreates_when_no_existing(db_session, monkeypatch):
    d = _device(db_session)
    alert_evaluator._last_trap_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps",
                        lambda hours=0.25: [_trap(d.ip_address, _LINK_DOWN, ifindex=3)])
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    alerts = _open_iface_down(db_session, d.id)
    assert len(alerts) == 1
    assert "linkDown trap" in alerts[0].message
    assert "ifIndex 3" in (alerts[0].note or "")


def test_linkdown_annotates_existing(db_session, monkeypatch):
    d = _device(db_session)
    existing = Alert(alert_type=AlertType.interface_down, message="polled down",
                     device_id=d.id, status=AlertStatus.open)
    db_session.add(existing)
    db_session.commit()
    alert_evaluator._last_trap_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps",
                        lambda hours=0.25: [_trap(d.ip_address, _LINK_DOWN)])
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    # no second alert; existing got annotated
    assert len(_open_iface_down(db_session, d.id)) == 1
    db_session.refresh(existing)
    assert "linkDown trap" in (existing.note or "")


def test_linkup_annotates_existing(db_session, monkeypatch):
    d = _device(db_session)
    existing = Alert(alert_type=AlertType.interface_down, message="down",
                     device_id=d.id, status=AlertStatus.open)
    db_session.add(existing)
    db_session.commit()
    alert_evaluator._last_trap_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps",
                        lambda hours=0.25: [_trap(d.ip_address, _LINK_UP)])
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    db_session.refresh(existing)
    assert "linkUp trap" in (existing.note or "")
    # linkUp never creates an alert
    assert len(_open_iface_down(db_session, d.id)) == 1


def test_unknown_device_ignored(db_session, monkeypatch):
    d = _device(db_session)
    alert_evaluator._last_trap_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps",
                        lambda hours=0.25: [_trap("192.168.99.99", _LINK_DOWN)])
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    assert _open_iface_down(db_session) == []


def test_non_link_trap_ignored(db_session, monkeypatch):
    d = _device(db_session)
    alert_evaluator._last_trap_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps",
                        lambda hours=0.25: [_trap(d.ip_address, "1.3.6.1.6.3.1.1.5.1")])  # coldStart
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    assert _open_iface_down(db_session) == []


def test_watermark_dedups_repeats(db_session, monkeypatch):
    d = _device(db_session)
    alert_evaluator._last_trap_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
    trap = _trap(d.ip_address, _LINK_DOWN)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps", lambda hours=0.25: [trap])
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    # second pass with the same trap: ts <= watermark -> no duplicate
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    assert len(_open_iface_down(db_session, d.id)) == 1


def test_suppressed_device_blocks_trap_alert(db_session, monkeypatch):
    from models import MaintenanceWindow
    d = _device(db_session)
    now = datetime.now(timezone.utc)
    db_session.add(MaintenanceWindow(device_id=d.id, start_at=now - timedelta(minutes=1),
                                     end_at=now + timedelta(hours=1)))
    db_session.commit()
    alert_evaluator._load_suppression(db_session)
    alert_evaluator._last_trap_ts = now - timedelta(minutes=10)
    monkeypatch.setattr(alert_evaluator, "_fetch_recent_traps",
                        lambda hours=0.25: [_trap(d.ip_address, _LINK_DOWN)])
    alert_evaluator._correlate_traps(db_session, [d])
    db_session.commit()
    assert _open_iface_down(db_session, d.id) == []
    alert_evaluator._suppress_all = False
    alert_evaluator._suppressed_devices = set()
