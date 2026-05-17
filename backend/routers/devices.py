from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from auth import get_current_user, require_role
from database import get_db
from models import Device, User
from schemas import DeviceCreate, DeviceUpdate, DeviceResponse, DeviceCredentialsResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=List[DeviceResponse])
def list_devices(
    skip: int = 0, limit: int = 100, enabled_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Device)
    if enabled_only:
        q = q.filter(Device.enabled == True)
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
