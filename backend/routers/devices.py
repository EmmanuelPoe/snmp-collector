from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Optional

import httpx

from auth import get_current_user, require_role
from config import settings
from database import get_db
from models import Device, User
from schemas import DeviceCreate, DeviceUpdate, DeviceResponse, DeviceCredentialsResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["devices"])


def _manager_headers() -> dict:
    return {"Authorization": f"Bearer {settings.manager_api_key}"}


def _resolve_agent_id(device: Device) -> Optional[str]:
    """The agent assigned to the device, or any online agent as a fallback."""
    if device.assigned_agent_id:
        return device.assigned_agent_id
    try:
        resp = httpx.get(f"{settings.manager_url}/agents", headers=_manager_headers(), timeout=5)
        resp.raise_for_status()
        for agent in resp.json():
            if agent.get("status") == "online" and agent.get("agent_id"):
                return agent["agent_id"]
    except httpx.RequestError:
        return None
    return None


@router.get("/tags", response_model=List[str])
def list_tags(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = db.query(Device.tags).all()
    all_tags = set()
    for (tags,) in rows:
        if tags:
            all_tags.update(tags)
    return sorted(all_tags)


@router.get("", response_model=List[DeviceResponse])
def list_devices(
    skip: int = 0, limit: int = 100, enabled_only: bool = False,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Device)
    if enabled_only:
        q = q.filter(Device.enabled == True)
    if tag:
        q = q.filter(cast(Device.tags, JSONB).contains([tag]))
    return q.offset(skip).limit(limit).all()


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    device: DeviceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    existing = db.query(Device).filter(Device.name == device.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Device '{device.name}' already exists")
    db_device = Device(**device.model_dump())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    device_update: DeviceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")
    for field, value in device_update.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    db.commit()
    db.refresh(device)
    return device


@router.get("/{device_id}/credentials", response_model=DeviceCredentialsResponse)
def get_device_credentials(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")
    return device


@router.post("/{device_id}/walk")
def walk_device_oids(
    device_id: int,
    base_oid: str = "1.3.6.1.2.1",
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    """Enqueue an on-demand SNMP walk on the device's agent (MIB browser).
    Returns a command_id to poll for the result."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")
    agent_id = _resolve_agent_id(device)
    if not agent_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No online agent available to perform the walk")
    params = {
        "device": {
            "id": str(device.id),
            "ip": device.ip_address,
            "snmp_version": device.snmp_version,
            "snmp_community": device.snmp_community,
            "snmp_port": device.snmp_port,
            "username": device.username,
            "auth_protocol": device.auth_protocol,
            "auth_password": device.auth_password,
            "priv_protocol": device.priv_protocol,
            "priv_password": device.priv_password,
        },
        "base_oid": base_oid,
        "max_rows": 500,
    }
    try:
        resp = httpx.post(f"{settings.manager_url}/agents/{agent_id}/commands",
                          json={"type": "walk", "params": params},
                          headers=_manager_headers(), timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Manager error: {exc}")
    return resp.json()


@router.get("/walk/{command_id}")
def get_walk_result(
    command_id: str,
    _: User = Depends(get_current_user),
):
    try:
        resp = httpx.get(f"{settings.manager_url}/commands/{command_id}",
                         headers=_manager_headers(), timeout=10)
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Walk command not found or expired")
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Manager error: {exc}")
    return resp.json()


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")
    db.delete(device)
    db.commit()
