from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import CollectionConfig, CollectionSchedule, Device
from schemas import (
    CollectionConfigCreate,
    CollectionConfigResponse,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse
)
from services.prometheus import reload_prometheus_config
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["configuration"])


# ===== OID Configuration =====

@router.get("/oids", response_model=List[CollectionConfigResponse])
def list_oids(
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """List SNMP OID configurations"""
    query = db.query(CollectionConfig)
    if enabled_only:
        query = query.filter(CollectionConfig.enabled == True)
    configs = query.all()
    return configs


@router.post("/oids", response_model=CollectionConfigResponse, status_code=status.HTTP_201_CREATED)
def create_oid_config(config: CollectionConfigCreate, db: Session = Depends(get_db)):
    """Add new SNMP OID to collect"""
    # Check if OID already exists
    existing = db.query(CollectionConfig).filter(CollectionConfig.oid == config.oid).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"OID '{config.oid}' already exists"
        )
    
    db_config = CollectionConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    logger.info(f"Created OID config: {db_config.oid_name} ({db_config.oid})")
    return db_config


@router.delete("/oids/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_oid_config(config_id: int, db: Session = Depends(get_db)):
    """Remove SNMP OID configuration"""
    config = db.query(CollectionConfig).filter(CollectionConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OID configuration with ID {config_id} not found"
        )
    
    logger.info(f"Deleting OID config: {config.oid_name} ({config.oid})")
    db.delete(config)
    db.commit()
    return None


# ===== Collection Schedule =====

@router.get("/schedule/{device_id}", response_model=ScheduleResponse)
def get_schedule(device_id: int, db: Session = Depends(get_db)):
    """Get collection schedule for a device"""
    schedule = db.query(CollectionSchedule).filter(
        CollectionSchedule.device_id == device_id
    ).first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule for device ID {device_id} not found"
        )
    
    return schedule


@router.put("/schedule/{device_id}", response_model=ScheduleResponse)
def update_schedule(
    device_id: int,
    schedule_update: ScheduleUpdate,
    db: Session = Depends(get_db)
):
    """Update collection schedule for a device"""
    schedule = db.query(CollectionSchedule).filter(
        CollectionSchedule.device_id == device_id
    ).first()
    
    if not schedule:
        # Create schedule if it doesn't exist
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device with ID {device_id} not found"
            )
        
        schedule = CollectionSchedule(device_id=device_id)
        db.add(schedule)
    
    # Update fields
    update_data = schedule_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)
    
    db.commit()
    db.refresh(schedule)
    
    logger.info(f"Updated schedule for device ID {device_id}: {schedule.interval_seconds}s")
    return schedule


@router.post("/schedule", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    """Create collection schedule for a device"""
    # Verify device exists
    device = db.query(Device).filter(Device.id == schedule.device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {schedule.device_id} not found"
        )
    
    # Check if schedule already exists
    existing = db.query(CollectionSchedule).filter(
        CollectionSchedule.device_id == schedule.device_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule for device ID {schedule.device_id} already exists"
        )
    
    db_schedule = CollectionSchedule(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    logger.info(f"Created schedule for device ID {schedule.device_id}")
    return db_schedule


# ===== Prometheus Configuration =====

@router.post("/reload")
async def reload_config():
    """Reload SNMP Exporter configuration"""
    try:
        success = await reload_prometheus_config()
        if success:
            logger.info("SNMP Exporter configuration reloaded successfully")
            return {"message": "Configuration reloaded successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reload configuration"
            )
    except Exception as e:
        logger.error(f"Error reloading configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reloading configuration: {str(e)}"
        )
