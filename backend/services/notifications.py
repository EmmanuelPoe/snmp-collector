"""Outbound alert notifications (Slack / generic webhook).

Fired fire-and-forget from the alert evaluator when a new alert is created. A
slow or dead channel must never block or crash evaluation, so every send is
wrapped and bounded by a short timeout.
"""
import logging

import httpx

from models import NotificationChannel, NotificationChannelType

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 3


def _enum_value(v) -> str:
    return v.value if hasattr(v, "value") else v


def _slack_payload(alert) -> dict:
    severity = _enum_value(alert.severity).upper()
    alert_type = _enum_value(alert.alert_type).replace("_", " ")
    return {"text": f":rotating_light: [{severity}] {alert_type} — {alert.message}"}


def _webhook_payload(alert) -> dict:
    return {
        "id": alert.id,
        "alert_type": _enum_value(alert.alert_type),
        "severity": _enum_value(alert.severity),
        "message": alert.message,
        "device_id": alert.device_id,
        "agent_id": alert.agent_id,
        "status": _enum_value(alert.status),
        "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
    }


def _matches(channel: NotificationChannel, alert) -> bool:
    sev_filter = channel.severity_filter or []
    if not sev_filter:  # empty = all severities
        return True
    return _enum_value(alert.severity) in sev_filter


def dispatch_alert(db, alert) -> None:
    """Send `alert` to every enabled channel whose severity filter matches."""
    channels = db.query(NotificationChannel).filter(NotificationChannel.enabled == True).all()
    for channel in channels:
        if not _matches(channel, alert):
            continue
        if _enum_value(channel.type) == NotificationChannelType.slack.value:
            payload = _slack_payload(alert)
        else:
            payload = _webhook_payload(alert)
        try:
            httpx.post(channel.url, json=payload, timeout=_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning("notification to channel %s (%s) failed: %s",
                           channel.id, channel.name, exc)
