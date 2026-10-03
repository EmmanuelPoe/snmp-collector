import httpx
from auth import get_current_user
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from logging_json import correlation_headers, get_logger
from models import Alert, AlertSeverity, AlertStatus, AlertType, Device, User
from sqlalchemy import case, func
from sqlalchemy.orm import Session

logger = get_logger(__name__)
router = APIRouter(prefix="/fleet", tags=["fleet"])

TOP_KEYS = ("top_by_traffic", "top_by_utilization")


def _manager_headers() -> dict:
    return {**correlation_headers(), "Authorization": f"Bearer {settings.manager_api_key}"}


def _agent_counts() -> dict | None:
    """Agent roll-up from the manager; None when it is unreachable so a manager
    outage degrades one tile rather than failing the whole summary."""
    try:
        resp = httpx.get(f"{settings.manager_url}/internal/agents", headers=_manager_headers(), timeout=3)
        resp.raise_for_status()
        agents = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("fleet summary: agent roll-up unavailable: %s", exc)
        return None
    online = sum(1 for a in agents if a.get("status") == "online")
    return {"total": len(agents), "online": online, "offline": len(agents) - online}


@router.get("/summary")
def fleet_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """One cheap call that answers "how is the estate?" regardless of fleet size.

    A device is `down` with an open device_unreachable alert, `degraded` with any
    other open alert, otherwise `up`. Disabled devices are counted apart so they
    never read as healthy."""
    total = db.query(func.count(Device.id)).scalar() or 0
    enabled = db.query(func.count(Device.id)).filter(Device.enabled == True).scalar() or 0  # noqa: E712

    per_device = (
        db.query(
            Alert.device_id,
            func.max(case((Alert.alert_type == AlertType.device_unreachable, 1), else_=0)),
        )
        .join(Device, Device.id == Alert.device_id)
        .filter(Alert.status == AlertStatus.open, Device.enabled == True)  # noqa: E712
        .group_by(Alert.device_id)
        .all()
    )
    down = sum(1 for _id, unreachable in per_device if unreachable)
    degraded = len(per_device) - down

    open_q = db.query(Alert).filter(Alert.status == AlertStatus.open)
    by_severity = dict(
        db.query(Alert.severity, func.count(Alert.id))
        .filter(Alert.status == AlertStatus.open)
        .group_by(Alert.severity)
        .all()
    )

    def _sev(s: AlertSeverity) -> int:
        return by_severity.get(s, 0)

    return {
        "devices": {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "up": enabled - down - degraded,
            "degraded": degraded,
            "down": down,
        },
        "alerts": {
            "open": sum(by_severity.values()),
            "critical": _sev(AlertSeverity.critical),
            "warning": _sev(AlertSeverity.warning),
            "info": _sev(AlertSeverity.info),
            "unacknowledged": open_q.filter(Alert.acknowledged_at.is_(None)).count(),
        },
        "agents": _agent_counts(),
    }


@router.get("/traffic")
def fleet_traffic(
    hours: float = Query(default=1.0, gt=0, le=24),
    top: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Fleet throughput series + top-N interfaces, device names resolved."""
    try:
        resp = httpx.get(
            f"{settings.manager_url}/internal/metrics/fleet-traffic",
            params={"hours": hours, "top": top},
            headers=_manager_headers(),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        ips = {row["device_ip"] for key in TOP_KEYS for row in data[key]}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.warning("fleet traffic: manager query failed: %s", exc)
        raise HTTPException(status_code=503, detail="Metrics store unavailable")

    devices = {}
    if ips:
        for d in db.query(Device.id, Device.name, Device.ip_address).filter(Device.ip_address.in_(ips)):
            devices.setdefault(d.ip_address, d)
    for key in TOP_KEYS:
        for row in data[key]:
            d = devices.get(row["device_ip"])
            row["device_id"] = d.id if d else None
            row["device_name"] = d.name if d else row["device_ip"]
    return data
