from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Device, CollectionSchedule
from schemas import DeviceCreate, DeviceUpdate, DeviceResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=List[DeviceResponse])
def list_devices(
    skip: int = 0,
    limit: int = 100,
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all devices"""
    query = db.query(Device)
    if enabled_only:
        query = query.filter(Device.enabled == True)
    devices = query.offset(skip).limit(limit).all()
    return devices


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    """Create a new device"""
    # Check if device name already exists
    existing = db.query(Device).filter(Device.name == device.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with name '{device.name}' already exists"
        )
    
    # Create device
    db_device = Device(**device.model_dump())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    
    # Create default collection schedule
    schedule = CollectionSchedule(
        device_id=db_device.id,
        interval_seconds=60,
        enabled=True
    )
    db.add(schedule)
    db.commit()
    
    logger.info(f"Created device: {db_device.name} (ID: {db_device.id})")
    return db_device


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db)):
    """Get device by ID"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found"
        )
    return device


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    device_update: DeviceUpdate,
    db: Session = Depends(get_db)
):
    """Update device"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found"
        )
    
    # Update only provided fields
    update_data = device_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)
    
    db.commit()
    db.refresh(device)
    logger.info(f"Updated device: {device.name} (ID: {device.id})")
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    """Delete device"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found"
        )
    
    logger.info(f"Deleting device: {device.name} (ID: {device.id})")
    db.delete(device)
    db.commit()
    return None
