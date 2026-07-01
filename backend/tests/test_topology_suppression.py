"""Unit tests for Step 13 gateway-rooted BFS dependency suppression."""
import alert_evaluator
from models import Alert, AlertStatus, AlertType, Device, TopologyEdge


def _open_count(db, alert_type):
    return db.query(Alert).filter(
        Alert.alert_type == alert_type, Alert.status == AlertStatus.open
    ).count()


def _enable(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "topology_suppression_enabled", True)
    # Suppression state is module-level and mutated per pass; reset it.
    alert_evaluator._suppressed_devices = set()
    alert_evaluator._suppress_all = False


def _chain(db):
    """root(core) -- a -- b, resolved edges both ways. Returns the three devices."""
    root = Device(name="root", ip_address="10.0.0.1", enabled=True, tags=["core"])
    a = Device(name="a", ip_address="10.0.0.2", enabled=True, tags=[])
    b = Device(name="b", ip_address="10.0.0.3", enabled=True, tags=[])
    db.add_all([root, a, b])
    db.commit()
    db.add(TopologyEdge(local_device_id=root.id, remote_device_id=a.id))
    db.add(TopologyEdge(local_device_id=a.id, remote_device_id=b.id))
    db.commit()
    return root, a, b


def test_bfs_depths_multisource():
    adj = {1: {2}, 2: {1, 3}, 3: {2}}
    depth = alert_evaluator._bfs_depths(adj, {1})
    assert depth == {1: 0, 2: 1, 3: 2}


def test_roots_prefers_tagged_over_degree(db_session):
    root, a, b = _chain(db_session)
    adj = {root.id: {a.id}, a.id: {root.id, b.id}, b.id: {a.id}}
    # 'a' has the highest degree, but 'root' is tagged core -> tag wins.
    assert alert_evaluator._topology_roots([root, a, b], adj) == {root.id}


def test_disabled_by_default_no_suppression(db_session, monkeypatch):
    root, a, b = _chain(db_session)
    # flag defaults False; even with both down, nothing is suppressed
    alert_evaluator._suppressed_devices = set()
    alert_evaluator._apply_topology_suppression(db_session, [root, a, b], {a.id, b.id})
    assert b.id not in alert_evaluator._suppressed_devices


def test_child_suppressed_when_parent_down(db_session, monkeypatch):
    _enable(monkeypatch)
    root, a, b = _chain(db_session)
    # a and b both unreachable, root up -> a is root cause, b is collateral
    alert_evaluator._apply_topology_suppression(db_session, [root, a, b], {a.id, b.id})
    assert b.id in alert_evaluator._suppressed_devices
    assert a.id not in alert_evaluator._suppressed_devices
    assert root.id not in alert_evaluator._suppressed_devices


def test_child_not_suppressed_when_parent_up(db_session, monkeypatch):
    _enable(monkeypatch)
    root, a, b = _chain(db_session)
    # only b is down; its parent a is up -> b is a genuine root cause
    alert_evaluator._apply_topology_suppression(db_session, [root, a, b], {b.id})
    assert b.id not in alert_evaluator._suppressed_devices


def test_root_never_suppressed(db_session, monkeypatch):
    _enable(monkeypatch)
    root, a, b = _chain(db_session)
    alert_evaluator._apply_topology_suppression(db_session, [root, a, b], {root.id})
    assert root.id not in alert_evaluator._suppressed_devices


def test_check_device_unreachable_suppresses_collateral_alert(db_session, monkeypatch):
    _enable(monkeypatch)
    root, a, b = _chain(db_session)

    # root reachable, a and b unreachable (no interfaces returned)
    def _rates(ip):
        if ip == root.ip_address:
            return {"interfaces": {"eth0": {"status": "up"}}}
        return {"interfaces": {}}
    monkeypatch.setattr(alert_evaluator, "_fetch_rates", _rates)

    alert_evaluator._check_device_unreachable(db_session, [root, a, b])
    db_session.commit()

    # Only 'a' (root cause) alerts; 'b' is suppressed as collateral.
    open_devs = {al.device_id for al in db_session.query(Alert).filter(
        Alert.alert_type == AlertType.device_unreachable,
        Alert.status == AlertStatus.open).all()}
    assert a.id in open_devs
    assert b.id not in open_devs
    assert _open_count(db_session, AlertType.device_unreachable) == 1
