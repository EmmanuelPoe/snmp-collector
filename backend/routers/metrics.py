from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import duckdb

from auth import get_current_user
from database import get_db
from models import Device, User
from schemas import MetricResponse
from config import settings

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _duckdb() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(settings.duckdb_path, read_only=True)


def _device_ip(device_id: int, db: Session) -> str:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device.ip_address


def _rows_to_metrics(rows: list[tuple], device_id: int) -> List[MetricResponse]:
    return [
        MetricResponse(
            id=i,
            device_id=device_id,
            timestamp=row[6],
            interface_name=row[2],
            interface_index=None,
            oid=row[4],
            oid_name=row[3],
            value=float(row[5]) if row[5] is not None else None,
            value_type="gauge",
        )
        for i, row in enumerate(rows)
    ]


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

    conditions = ["device_ip = ?"]
    params: list = [device_ip]
    if interface_name:
        conditions.append("interface_name = ?")
        params.append(interface_name)
    if oid_name:
        conditions.append("oid_name = ?")
        params.append(oid_name)
    if start_time:
        conditions.append("collected_at >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("collected_at <= ?")
        params.append(end_time)
    params.append(limit)

    conn = _duckdb()
    try:
        rows = conn.execute(
            "SELECT agent_id, device_ip, interface_name, oid_name, oid, value, collected_at "
            f"FROM snmp_polls WHERE {' AND '.join(conditions)} "
            "ORDER BY collected_at DESC LIMIT ?",
            params,
        ).fetchall()
    finally:
        conn.close()
    return _rows_to_metrics(rows, device_id)


@router.get("/latest/{device_id}", response_model=List[MetricResponse])
def get_latest_metrics(device_id: int, limit: int = 100, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    device_ip = _device_ip(device_id, db)
    conn = _duckdb()
    try:
        rows = conn.execute(
            "SELECT agent_id, device_ip, interface_name, oid_name, oid, value, collected_at "
            "FROM snmp_polls WHERE device_ip = ? ORDER BY collected_at DESC LIMIT ?",
            [device_ip, limit],
        ).fetchall()
    finally:
        conn.close()
    return _rows_to_metrics(rows, device_id)


@router.get("/available/{device_id}")
def get_available_metrics(device_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    device_ip = _device_ip(device_id, db)
    conn = _duckdb()
    try:
        ifaces = conn.execute(
            "SELECT DISTINCT interface_name FROM snmp_polls "
            "WHERE device_ip = ? AND interface_name IS NOT NULL",
            [device_ip],
        ).fetchall()
        oids = conn.execute(
            "SELECT DISTINCT oid_name FROM snmp_polls WHERE device_ip = ? AND oid_name IS NOT NULL",
            [device_ip],
        ).fetchall()
    finally:
        conn.close()
    return {
        "modules": {
            "if_mib": {
                "interfaces": sorted(r[0] for r in ifaces),
                "metrics": sorted(r[0] for r in oids),
            }
        }
    }


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

    conn = _duckdb()
    try:
        rows = conn.execute(
            "SELECT agent_id, device_ip, interface_name, oid_name, oid, value, collected_at "
            "FROM snmp_polls WHERE device_ip = ? AND interface_name = ? "
            "AND collected_at >= ? ORDER BY collected_at",
            [device_ip, interface_name, start_time],
        ).fetchall()
    finally:
        conn.close()

    return {
        "device_id": device_id,
        "interface_name": interface_name,
        "time_range": {"start": start_time, "end": end_time, "hours": hours},
        "metrics": [
            {
                "device_id": device_id,
                "timestamp": row[6],
                "interface_name": row[2],
                "oid_name": row[3],
                "oid": row[4],
                "value": float(row[5]) if row[5] is not None else None,
                "id": i,
            }
            for i, row in enumerate(rows)
        ],
    }
