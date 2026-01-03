from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime, timedelta
from database import get_db
from models import SNMPMetric, Device
from schemas import MetricResponse, MetricQuery
from services.collector import collect_device_metrics
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=List[MetricResponse])
def query_metrics(
    device_id: int = None,
    interface_name: str = None,
    oid: str = None,
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """Query metrics with filters"""
    query = db.query(SNMPMetric)
    
    # Apply filters
    if device_id:
        query = query.filter(SNMPMetric.device_id == device_id)
    if interface_name:
        query = query.filter(SNMPMetric.interface_name == interface_name)
    if oid:
        query = query.filter(SNMPMetric.oid == oid)
    if start_time:
        query = query.filter(SNMPMetric.timestamp >= start_time)
    if end_time:
        query = query.filter(SNMPMetric.timestamp <= end_time)
    
    # Order by timestamp descending and limit
    metrics = query.order_by(desc(SNMPMetric.timestamp)).limit(limit).all()
    return metrics


@router.get("/latest/{device_id}", response_model=List[MetricResponse])
def get_latest_metrics(
    device_id: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get latest metrics for a device"""
    # Verify device exists
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found"
        )
    
    metrics = db.query(SNMPMetric).filter(
        SNMPMetric.device_id == device_id
    ).order_by(desc(SNMPMetric.timestamp)).limit(limit).all()
    
    return metrics


@router.get("/interfaces/{device_id}")
def get_device_interfaces(device_id: int, db: Session = Depends(get_db)):
    """Get unique interfaces for a device"""
    # Verify device exists
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found"
        )
    
    # Get distinct interfaces
    interfaces = db.query(
        SNMPMetric.interface_name,
        SNMPMetric.interface_index
    ).filter(
        SNMPMetric.device_id == device_id,
        SNMPMetric.interface_name.isnot(None)
    ).distinct().all()
    
    return [
        {
            "interface_name": interface_name,
            "interface_index": interface_index
        }
        for interface_name, interface_index in interfaces
    ]


@router.post("/collect/{device_id}")
async def trigger_collection(
    device_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger manual metric collection for a device"""
    # Verify device exists and is enabled
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found"
        )
    
    if not device.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device '{device.name}' is disabled"
        )
    
    # Trigger collection in background
    background_tasks.add_task(collect_device_metrics, device_id)
    
    logger.info(f"Triggered manual collection for device: {device.name} (ID: {device_id})")
    return {
        "message": f"Collection triggered for device '{device.name}'",
        "device_id": device_id
    }


@router.get("/stats/{device_id}/{interface_name}")
def get_interface_stats(
    device_id: int,
    interface_name: str,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get interface statistics for the last N hours"""
    # Verify device exists
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found"
        )
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    # Query metrics
    metrics = db.query(SNMPMetric).filter(
        SNMPMetric.device_id == device_id,
        SNMPMetric.interface_name == interface_name,
        SNMPMetric.timestamp >= start_time,
        SNMPMetric.timestamp <= end_time
    ).order_by(SNMPMetric.timestamp).all()
    
    return {
        "device_id": device_id,
        "device_name": device.name,
        "interface_name": interface_name,
        "time_range": {
            "start": start_time,
            "end": end_time,
            "hours": hours
        },
        "metrics": [MetricResponse.model_validate(m) for m in metrics]
    }
