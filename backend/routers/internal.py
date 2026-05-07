from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_manager_key
from database import get_db
from models import Device

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/devices")
def get_devices_for_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(require_manager_key),
):
    devices = db.query(Device).filter(
        Device.assigned_agent_id == agent_id,
        Device.enabled == True,
    ).all()
    return [_to_device_config(d) for d in devices]


def _to_device_config(d: Device) -> dict:
    return {
        "id": str(d.id),
        "ip": d.ip_address,
        "hostname": d.name,
        "snmp_version": d.snmp_version,
        "snmp_community": d.snmp_community if d.snmp_version == "2c" else None,
        "snmp_port": d.snmp_port,
        "username": d.username,
        "auth_protocol": d.auth_protocol,
        "auth_password": d.auth_password,
        "priv_protocol": d.priv_protocol,
        "priv_password": d.priv_password,
    }
