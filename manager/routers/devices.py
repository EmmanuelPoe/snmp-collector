import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from models import AddDeviceRequest, DeviceResponse
from auth import require_api_key
from db import query, execute

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
def list_devices(_: str = Depends(require_api_key)):
    rows = query(
        "SELECT id, ip, hostname, snmp_version, username, auth_protocol, "
        "priv_protocol, assigned_agent_id, created_at, last_polled_at FROM devices"
    )
    return [_to_response(r) for r in rows]


@router.post("", response_model=DeviceResponse, status_code=201)
async def add_device(req: AddDeviceRequest, _: str = Depends(require_api_key)):
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await execute(
        "INSERT INTO devices VALUES (?,?,?,'v3',?,?,?,?,?,?,?,NULL)",
        [
            device_id, req.ip, req.hostname, req.username,
            req.auth_protocol, req.auth_password,
            req.priv_protocol, req.priv_password,
            req.assigned_agent_id, now,
        ],
    )
    rows = query(
        "SELECT id, ip, hostname, snmp_version, username, auth_protocol, "
        "priv_protocol, assigned_agent_id, created_at, last_polled_at "
        "FROM devices WHERE id = ?",
        [device_id],
    )
    return _to_response(rows[0])


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, _: str = Depends(require_api_key)):
    if not query("SELECT id FROM devices WHERE id = ?", [device_id]):
        raise HTTPException(status_code=404, detail="Device not found")
    await execute("DELETE FROM devices WHERE id = ?", [device_id])


def _to_response(row: tuple) -> DeviceResponse:
    return DeviceResponse(
        id=row[0], ip=row[1], hostname=row[2], snmp_version=row[3],
        username=row[4], auth_protocol=row[5], priv_protocol=row[6],
        assigned_agent_id=row[7], created_at=row[8], last_polled_at=row[9],
    )
