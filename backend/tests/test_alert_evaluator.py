"""Unit tests for Phase 0 alert-evaluator changes: virtual-interface denylist
and error-rate alerting."""
import alert_evaluator
from models import Alert, AlertRule, AlertType, AlertStatus, Device


def _open_count(db, alert_type):
    return db.query(Alert).filter(
        Alert.alert_type == alert_type, Alert.status == AlertStatus.open
    ).count()


def test_is_virtual_iface():
    assert alert_evaluator._is_virtual_iface("erspan0")
    assert alert_evaluator._is_virtual_iface("gre0")
    assert alert_evaluator._is_virtual_iface("tunl0")
    assert alert_evaluator._is_virtual_iface("lo")
    assert not alert_evaluator._is_virtual_iface("eth0")
    assert not alert_evaluator._is_virtual_iface("GigabitEthernet0/1")


def test_interface_down_skips_virtual(db_session, monkeypatch):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()

    monkeypatch.setattr(alert_evaluator, "_fetch_rates", lambda ip: {
        "interfaces": {
            "erspan0": {"status": "down"},
            "gre0": {"status": "down"},
            "eth0": {"status": "up"},
        }
    })
    alert_evaluator._check_interface_down(db_session, [device])
    assert _open_count(db_session, AlertType.interface_down) == 0


def test_interface_down_fires_for_real_iface(db_session, monkeypatch):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()

    monkeypatch.setattr(alert_evaluator, "_fetch_rates", lambda ip: {
        "interfaces": {"eth0": {"status": "down"}, "erspan0": {"status": "down"}}
    })
    alert_evaluator._check_interface_down(db_session, [device])
    assert _open_count(db_session, AlertType.interface_down) == 1


def test_error_rate_fires_above_threshold(db_session, monkeypatch):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()
    db_session.add(AlertRule(device_id=device.id, error_rate=0.1, enabled=True))
    db_session.commit()

    # window = 0.1h = 360s; 100 errors / 360s = 0.278 errors/sec > 0.1 threshold
    monkeypatch.setattr(alert_evaluator, "_fetch_rates", lambda ip: {
        "interfaces": {"eth0": {"error_count": 100}}
    })
    alert_evaluator._check_error_rate(db_session, [device])
    assert _open_count(db_session, AlertType.error_rate) == 1


def test_error_rate_quiet_below_threshold(db_session, monkeypatch):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()
    db_session.add(AlertRule(device_id=device.id, error_rate=1.0, enabled=True))
    db_session.commit()

    # 100 / 360 = 0.278 errors/sec < 1.0 threshold
    monkeypatch.setattr(alert_evaluator, "_fetch_rates", lambda ip: {
        "interfaces": {"eth0": {"error_count": 100}}
    })
    alert_evaluator._check_error_rate(db_session, [device])
    assert _open_count(db_session, AlertType.error_rate) == 0


def test_error_rate_skips_virtual_iface(db_session, monkeypatch):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()
    db_session.add(AlertRule(device_id=device.id, error_rate=0.01, enabled=True))
    db_session.commit()

    monkeypatch.setattr(alert_evaluator, "_fetch_rates", lambda ip: {
        "interfaces": {"erspan0": {"error_count": 10000}}
    })
    alert_evaluator._check_error_rate(db_session, [device])
    assert _open_count(db_session, AlertType.error_rate) == 0


def test_error_rate_no_rule_no_alert(db_session, monkeypatch):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()

    monkeypatch.setattr(alert_evaluator, "_fetch_rates", lambda ip: {
        "interfaces": {"eth0": {"error_count": 100000}}
    })
    alert_evaluator._check_error_rate(db_session, [device])
    assert _open_count(db_session, AlertType.error_rate) == 0


def test_error_rate_resolves_when_back_to_normal(db_session, monkeypatch):
    device = Device(name="d1", ip_address="10.0.0.1", enabled=True)
    db_session.add(device)
    db_session.commit()
    db_session.add(AlertRule(device_id=device.id, error_rate=0.1, enabled=True))
    db_session.add(Alert(alert_type=AlertType.error_rate, message="old", device_id=device.id,
                         status=AlertStatus.open))
    db_session.commit()

    monkeypatch.setattr(alert_evaluator, "_fetch_rates", lambda ip: {
        "interfaces": {"eth0": {"error_count": 0}}
    })
    alert_evaluator._check_error_rate(db_session, [device])
    assert _open_count(db_session, AlertType.error_rate) == 0
