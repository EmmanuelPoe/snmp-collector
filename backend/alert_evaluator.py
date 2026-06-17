import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

from config import settings
from database import SessionLocal
from models import (
    Alert, AlertRule, AlertSeverity, AlertStatus, AlertType, Device, MaintenanceWindow,
)
from services import notifications

logger = logging.getLogger(__name__)

_RATES_LOOKBACK_HOURS = 0.1  # 6-minute window

# Maintenance suppression for the current evaluation pass. Set at the top of
# run_evaluation and read by _create_alert. The evaluator is single-threaded
# (one asyncio task) so module-level state is safe here. Suppression blocks the
# creation of NEW alerts only; existing alerts still resolve normally.
_suppress_all = False
_suppressed_devices: set = set()

# Linux virtual/system interfaces that are permanently down; never alert on them.
_VIRTUAL_IFACE_PREFIXES = ("erspan", "gre", "sit", "tunl", "ip6tnl", "bond", "lo")


def _is_virtual_iface(name: str) -> bool:
    return name.startswith(_VIRTUAL_IFACE_PREFIXES)


def _headers():
    return {"Authorization": f"Bearer {settings.manager_api_key}"}


def _open_alert_exists(db, alert_type: AlertType, device_id=None, agent_id=None) -> bool:
    q = db.query(Alert).filter(Alert.alert_type == alert_type, Alert.status == AlertStatus.open)
    if device_id is not None:
        q = q.filter(Alert.device_id == device_id)
    if agent_id is not None:
        q = q.filter(Alert.agent_id == agent_id)
    return q.first() is not None


_SEVERITY_BY_TYPE = {
    AlertType.device_unreachable: AlertSeverity.critical,
    AlertType.agent_offline: AlertSeverity.critical,
    AlertType.interface_down: AlertSeverity.warning,
    AlertType.bandwidth_threshold: AlertSeverity.warning,
    AlertType.error_rate: AlertSeverity.warning,
    AlertType.baseline_anomaly: AlertSeverity.warning,
}

# Baselines are a heavy 7-day query, so they are cached per device and refreshed
# at most once per TTL rather than recomputed on every 30s evaluation pass.
_BASELINE_TTL_SECONDS = 3600
_baseline_cache: dict = {}


def _is_suppressed(device_id) -> bool:
    if _suppress_all:
        return True
    return device_id is not None and device_id in _suppressed_devices


def _create_alert(db, alert_type: AlertType, message: str, device_id=None, agent_id=None):
    if _is_suppressed(device_id):
        return None
    alert = Alert(alert_type=alert_type, message=message, device_id=device_id,
                  agent_id=agent_id, status=AlertStatus.open,
                  severity=_SEVERITY_BY_TYPE.get(alert_type, AlertSeverity.info))
    db.add(alert)
    return alert


def _resolve_alerts(db, alert_type: AlertType, device_id=None, agent_id=None):
    q = db.query(Alert).filter(Alert.alert_type == alert_type, Alert.status == AlertStatus.open)
    if device_id is not None:
        q = q.filter(Alert.device_id == device_id)
    if agent_id is not None:
        q = q.filter(Alert.agent_id == agent_id)
    now = datetime.now(timezone.utc)
    for alert in q.all():
        alert.status = AlertStatus.resolved
        alert.resolved_at = now


def _fetch_rates(device_ip: str) -> dict:
    url = f"{settings.manager_url}/internal/metrics/rates"
    resp = httpx.get(url, params={"device_ip": device_ip, "hours": _RATES_LOOKBACK_HOURS},
                     headers=_headers(), timeout=5)
    resp.raise_for_status()
    return resp.json()


def _check_device_unreachable(db, devices: list):
    for device in devices:
        if not device.enabled:
            continue
        try:
            data = _fetch_rates(device.ip_address)
            if data.get("interfaces"):
                _resolve_alerts(db, AlertType.device_unreachable, device_id=device.id)
            else:
                if not _open_alert_exists(db, AlertType.device_unreachable, device_id=device.id):
                    _create_alert(db, AlertType.device_unreachable,
                                  f"{device.name} — no SNMP data received in last 5 minutes",
                                  device_id=device.id)
        except Exception as exc:
            logger.warning("device_unreachable check failed for %s: %s", device.name, exc)


def _check_interface_down(db, devices: list):
    for device in devices:
        if not device.enabled:
            continue
        try:
            data = _fetch_rates(device.ip_address)
            down = [n for n, i in data.get("interfaces", {}).items()
                    if i.get("status") == "down" and not _is_virtual_iface(n)]
            if down:
                names = ", ".join(down)
                existing = db.query(Alert).filter(
                    Alert.alert_type == AlertType.interface_down,
                    Alert.device_id == device.id,
                    Alert.status == AlertStatus.open,
                ).first()
                if existing:
                    existing.message = f"{device.name} — interfaces down: {names}"
                else:
                    _create_alert(db, AlertType.interface_down,
                                  f"{device.name} — interfaces down: {names}",
                                  device_id=device.id)
            else:
                _resolve_alerts(db, AlertType.interface_down, device_id=device.id)
        except Exception as exc:
            logger.warning("interface_down check failed for %s: %s", device.name, exc)


def _check_bandwidth_thresholds(db, devices: list):
    rules = {r.device_id: r for r in
             db.query(AlertRule).filter(AlertRule.enabled == True).all()}
    for device in devices:
        rule = rules.get(device.id)
        if not rule or not device.enabled:
            continue
        try:
            data = _fetch_rates(device.ip_address)
            fired = False
            for iface_name, iface in data.get("interfaces", {}).items():
                speed = iface.get("speed_bps")
                if not speed:
                    continue
                in_pct = iface.get("current_in_bps", 0) / speed * 100
                out_pct = iface.get("current_out_bps", 0) / speed * 100
                if rule.bandwidth_in_pct and in_pct > rule.bandwidth_in_pct:
                    fired = True
                    if not _open_alert_exists(db, AlertType.bandwidth_threshold, device_id=device.id):
                        _create_alert(db, AlertType.bandwidth_threshold,
                                      f"{device.name} — {iface_name} in at {in_pct:.1f}% utilization",
                                      device_id=device.id)
                    break
                if rule.bandwidth_out_pct and out_pct > rule.bandwidth_out_pct:
                    fired = True
                    if not _open_alert_exists(db, AlertType.bandwidth_threshold, device_id=device.id):
                        _create_alert(db, AlertType.bandwidth_threshold,
                                      f"{device.name} — {iface_name} out at {out_pct:.1f}% utilization",
                                      device_id=device.id)
                    break
            if not fired:
                _resolve_alerts(db, AlertType.bandwidth_threshold, device_id=device.id)
        except Exception as exc:
            logger.warning("bandwidth check failed for %s: %s", device.name, exc)


def _check_error_rate(db, devices: list):
    rules = {r.device_id: r for r in
             db.query(AlertRule).filter(AlertRule.enabled == True).all()}
    window_seconds = _RATES_LOOKBACK_HOURS * 3600
    for device in devices:
        rule = rules.get(device.id)
        if not rule or rule.error_rate is None or not device.enabled:
            continue
        try:
            data = _fetch_rates(device.ip_address)
            fired = False
            for iface_name, iface in data.get("interfaces", {}).items():
                if _is_virtual_iface(iface_name):
                    continue
                errors_per_sec = iface.get("error_count", 0) / window_seconds
                if errors_per_sec > rule.error_rate:
                    fired = True
                    if not _open_alert_exists(db, AlertType.error_rate, device_id=device.id):
                        _create_alert(db, AlertType.error_rate,
                                      f"{device.name} — {iface_name} at {errors_per_sec:.2f} errors/sec",
                                      device_id=device.id)
                    break
            if not fired:
                _resolve_alerts(db, AlertType.error_rate, device_id=device.id)
        except Exception as exc:
            logger.warning("error_rate check failed for %s: %s", device.name, exc)


def _fetch_baseline(device_ip: str) -> dict:
    url = f"{settings.manager_url}/internal/metrics/baseline"
    resp = httpx.get(url, params={"device_ip": device_ip, "days": settings.baseline_window_days},
                     headers=_headers(), timeout=20)
    resp.raise_for_status()
    return resp.json()


def _get_baseline(device_ip: str) -> dict:
    now = time.monotonic()
    cached = _baseline_cache.get(device_ip)
    if cached and now - cached[0] < _BASELINE_TTL_SECONDS:
        return cached[1]
    data = _fetch_baseline(device_ip)
    _baseline_cache[device_ip] = (now, data)
    return data


def _check_baseline_anomaly(db, devices: list):
    if not settings.baseline_anomaly_enabled:
        return
    mult = settings.baseline_multiplier
    min_samples = settings.baseline_min_samples
    for device in devices:
        if not device.enabled:
            continue
        try:
            rates = _fetch_rates(device.ip_address)
            baseline = _get_baseline(device.ip_address).get("interfaces", {})
            fired = False
            for name, iface in rates.get("interfaces", {}).items():
                if _is_virtual_iface(name):
                    continue
                b = baseline.get(name)
                if not b:
                    continue
                in_p95 = b.get("in_p95_bps") or 0
                out_p95 = b.get("out_p95_bps") or 0
                cur_in = iface.get("current_in_bps", 0)
                cur_out = iface.get("current_out_bps", 0)
                if in_p95 > 0 and b.get("in_samples", 0) >= min_samples and cur_in > in_p95 * mult:
                    fired = True
                    if not _open_alert_exists(db, AlertType.baseline_anomaly, device_id=device.id):
                        _create_alert(db, AlertType.baseline_anomaly,
                                      f"{device.name} — {name} inbound {cur_in:.0f} bps exceeds baseline p95 {in_p95:.0f} bps (x{mult})",
                                      device_id=device.id)
                    break
                if out_p95 > 0 and b.get("out_samples", 0) >= min_samples and cur_out > out_p95 * mult:
                    fired = True
                    if not _open_alert_exists(db, AlertType.baseline_anomaly, device_id=device.id):
                        _create_alert(db, AlertType.baseline_anomaly,
                                      f"{device.name} — {name} outbound {cur_out:.0f} bps exceeds baseline p95 {out_p95:.0f} bps (x{mult})",
                                      device_id=device.id)
                    break
            if not fired:
                _resolve_alerts(db, AlertType.baseline_anomaly, device_id=device.id)
        except Exception as exc:
            logger.warning("baseline check failed for %s: %s", device.name, exc)


# --- Trap correlation ---------------------------------------------------------

_SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"   # snmpTrapOID.0 — value is the trap type
_LINK_DOWN = "1.3.6.1.6.3.1.1.5.3"
_LINK_UP = "1.3.6.1.6.3.1.1.5.4"
_IFINDEX_PREFIX = "1.3.6.1.2.1.2.2.1.1"    # ifIndex.<n>

# High-water mark so each trap is correlated once. None = first pass: adopt the
# newest trap timestamp and skip history (no alert storm from old traps on boot).
_last_trap_ts = None


def _fetch_recent_traps(hours: float = 0.25) -> list:
    resp = httpx.get(f"{settings.manager_url}/internal/metrics/traps",
                     params={"hours": hours, "limit": 500}, headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _trap_type(varbinds: dict, trap_oid_col: str):
    return varbinds.get(_SNMP_TRAP_OID) or trap_oid_col


def _extract_ifindex(varbinds: dict):
    for key, val in varbinds.items():
        if key.startswith(_IFINDEX_PREFIX):
            return val
    return None


def _open_interface_down(db, device_id):
    return db.query(Alert).filter(
        Alert.alert_type == AlertType.interface_down,
        Alert.device_id == device_id,
        Alert.status == AlertStatus.open,
    ).first()


def _append_note(alert, note: str):
    if alert.note and note in alert.note:
        return
    alert.note = f"{alert.note}\n{note}" if alert.note else note


def _process_trap(db, device_map, trap, ts):
    import json
    try:
        varbinds = json.loads(trap.get("varbinds") or "{}")
    except (ValueError, TypeError):
        varbinds = {}
    ttype = _trap_type(varbinds, trap.get("trap_oid"))
    if ttype not in (_LINK_DOWN, _LINK_UP):
        return
    device = device_map.get(trap.get("device_ip"))
    if not device:
        return  # trap from an unknown device — nothing to correlate against

    ifindex = _extract_ifindex(varbinds)
    where = f"ifIndex {ifindex}" if ifindex else "an interface"
    stamp = ts.isoformat() if ts else "unknown time"
    existing = _open_interface_down(db, device.id)

    if ttype == _LINK_DOWN:
        note = f"linkDown trap at {stamp} ({where})"
        if existing:
            _append_note(existing, note)  # confirm/enrich the polled alert
        else:
            alert = _create_alert(db, AlertType.interface_down,
                                  f"{device.name} — linkDown trap ({where})",
                                  device_id=device.id)
            if alert is not None:
                alert.note = note
    else:  # linkUp — informational annotation on any open alert
        if existing:
            _append_note(existing, f"linkUp trap at {stamp} ({where})")


def _correlate_traps(db, devices: list):
    global _last_trap_ts
    try:
        traps = _fetch_recent_traps()
    except Exception as exc:
        logger.warning("trap correlation fetch failed: %s", exc)
        return

    parsed = [(_parse_ts(t.get("received_at")), t) for t in traps]
    parsed = [(ts, t) for ts, t in parsed if ts is not None]
    parsed.sort(key=lambda x: x[0])

    if _last_trap_ts is None:
        _last_trap_ts = parsed[-1][0] if parsed else datetime.now(timezone.utc)
        return

    device_map = {d.ip_address: d for d in devices}
    new_max = _last_trap_ts
    for ts, trap in parsed:
        if ts <= _last_trap_ts:
            continue
        _process_trap(db, device_map, trap, ts)
        if ts > new_max:
            new_max = ts
    _last_trap_ts = new_max


def _check_agent_offline(db):
    try:
        resp = httpx.get(f"{settings.manager_url}/agents", headers=_headers(), timeout=5)
        resp.raise_for_status()
        for agent in resp.json():
            agent_id = agent.get("agent_id")
            if not agent_id:
                continue
            if agent.get("status") == "offline":
                if not _open_alert_exists(db, AlertType.agent_offline, agent_id=agent_id):
                    hostname = agent.get("hostname") or agent_id[:12]
                    _create_alert(db, AlertType.agent_offline,
                                  f"Agent {hostname} has gone offline",
                                  agent_id=agent_id)
            else:
                _resolve_alerts(db, AlertType.agent_offline, agent_id=agent_id)
    except Exception as exc:
        logger.warning("agent_offline check failed: %s", exc)


def _load_suppression(db):
    """Populate maintenance-window suppression state for this pass."""
    global _suppress_all, _suppressed_devices
    now = datetime.now(timezone.utc)
    windows = db.query(MaintenanceWindow).filter(
        MaintenanceWindow.start_at <= now, MaintenanceWindow.end_at >= now).all()
    _suppress_all = any(w.device_id is None for w in windows)
    _suppressed_devices = {w.device_id for w in windows if w.device_id is not None}


def run_evaluation():
    db = SessionLocal()
    try:
        _load_suppression(db)
        devices = db.query(Device).all()
        _check_device_unreachable(db, devices)
        _check_interface_down(db, devices)
        _correlate_traps(db, devices)
        _check_bandwidth_thresholds(db, devices)
        _check_error_rate(db, devices)
        _check_baseline_anomaly(db, devices)
        _check_agent_offline(db)
        new_alerts = [o for o in db.new if isinstance(o, Alert)]
        db.commit()
        for alert in new_alerts:
            notifications.dispatch_alert(db, alert)
    except Exception as exc:
        logger.error("Alert evaluation error: %s", exc)
        db.rollback()
    finally:
        db.close()


async def evaluation_loop():
    while True:
        await asyncio.sleep(30)
        run_evaluation()
