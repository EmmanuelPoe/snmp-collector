from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import httpx

from auth import get_current_user
from database import get_db
from models import Device, User
from schemas import MetricResponse
from config import settings

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _manager_headers() -> dict:
    return {"Authorization": f"Bearer {settings.manager_api_key}"}


def _device_ip(device_id: int, db: Session) -> str:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device.ip_address


def _to_metrics(rows: list[dict], device_id: int) -> List[MetricResponse]:
    return [
        MetricResponse(
            id=i,
            device_id=device_id,
            timestamp=row["collected_at"],
            interface_name=row["interface_name"],
            interface_index=None,
            oid=row["oid"],
            oid_name=row["oid_name"],
            value=float(row["value"]) if row["value"] is not None else None,
            value_type="gauge",
        )
        for i, row in enumerate(rows)
    ]


def _manager_get(path: str, params: dict) -> list | dict:
    url = f"{settings.manager_url}/internal/metrics{path}"
    resp = httpx.get(url, params=params, headers=_manager_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


@router.get("", response_model=List[MetricResponse])
def query_metrics(
    device_id: Optional[int] = None,
    interface_name: Optional[str] = None,
    oid_name: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not device_id:
        return []
    device_ip = _device_ip(device_id, db)
    params = {"device_ip": device_ip, "limit": limit}
    if interface_name:
        params["interface_name"] = interface_name
    if oid_name:
        params["oid_name"] = oid_name
    if start_time:
        params["start_time"] = start_time.isoformat()
    if end_time:
        params["end_time"] = end_time.isoformat()
    rows = _manager_get("", params)
    return _to_metrics(rows, device_id)


@router.get("/latest/{device_id}", response_model=List[MetricResponse])
def get_latest_metrics(
    device_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device_ip = _device_ip(device_id, db)
    rows = _manager_get("", {"device_ip": device_ip, "limit": limit})
    return _to_metrics(rows, device_id)


@router.get("/available/{device_id}")
def get_available_metrics(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device_ip = _device_ip(device_id, db)
    return _manager_get("/available", {"device_ip": device_ip})


@router.get("/rates/{device_id}")
def get_interface_rates(
    device_id: int,
    hours: float = 1.0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device_ip = _device_ip(device_id, db)
    return _manager_get("/rates", {"device_ip": device_ip, "hours": hours})


@router.get("/history/{device_id}")
def get_interface_history(
    device_id: int,
    interface_name: str,
    hours: float = 1.0,
    buckets: int = 60,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device_ip = _device_ip(device_id, db)
    return _manager_get("/history", {
        "device_ip": device_ip,
        "interface_name": interface_name,
        "hours": hours,
        "buckets": buckets,
    })


@router.get("/stats/{device_id}/{interface_name}")
def get_interface_stats(
    device_id: int,
    interface_name: str,
    hours: int = 24,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import timedelta, timezone
    device_ip = _device_ip(device_id, db)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)
    rows = _manager_get("", {
        "device_ip": device_ip,
        "interface_name": interface_name,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "limit": 10000,
    })
    return {
        "device_id": device_id,
        "interface_name": interface_name,
        "time_range": {"start": start_time, "end": end_time, "hours": hours},
        "metrics": [
            {
                "device_id": device_id,
                "timestamp": row["collected_at"],
                "interface_name": row["interface_name"],
                "oid_name": row["oid_name"],
                "oid": row["oid"],
                "value": float(row["value"]) if row["value"] is not None else None,
                "id": i,
            }
            for i, row in enumerate(rows)
        ],
    }
