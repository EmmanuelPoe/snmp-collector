import asyncio
import logging
from datetime import datetime, timezone

import httpx

from config import settings
from database import SessionLocal
from models import Alert, AlertRule, AlertStatus, AlertType, Device

logger = logging.getLogger(__name__)

_RATES_LOOKBACK_HOURS = 0.1  # 6-minute window

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


def _create_alert(db, alert_type: AlertType, message: str, device_id=None, agent_id=None):
    db.add(Alert(alert_type=alert_type, message=message, device_id=device_id,
                 agent_id=agent_id, status=AlertStatus.open))


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


def run_evaluation():
    db = SessionLocal()
    try:
        devices = db.query(Device).all()
        _check_device_unreachable(db, devices)
        _check_interface_down(db, devices)
        _check_bandwidth_thresholds(db, devices)
        _check_error_rate(db, devices)
        _check_agent_offline(db)
        db.commit()
    except Exception as exc:
        logger.error("Alert evaluation error: %s", exc)
        db.rollback()
    finally:
        db.close()


async def evaluation_loop():
    while True:
        await asyncio.sleep(30)
        run_evaluation()
