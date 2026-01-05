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
    ScheduleResponse,
    ModuleConfigUpdate
)
from services.prometheus import (
    reload_prometheus_config, 
    get_available_modules, 
    get_module_config,
    update_module_config
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["configuration"])


# ===== Modules Configuration =====

@router.get("/modules", response_model=List[str])
def list_modules():
    """List available SNMP modules from snmp.yml"""
    return get_available_modules()

@router.get("/modules/{module_name}")
def get_module(module_name: str):
    """Get configuration for a specific module"""
    config = get_module_config(module_name)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{module_name}' not found"
        )
    return {"name": module_name, "yaml": config}

@router.put("/modules/{module_name}")
async def update_module(module_name: str, config: ModuleConfigUpdate):
    """Update configuration for a specific module"""
    try:
        if update_module_config(module_name, config.yaml_content):
            await reload_prometheus_config()
            return {"message": f"Module '{module_name}' updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update module configuration"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating module {module_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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
