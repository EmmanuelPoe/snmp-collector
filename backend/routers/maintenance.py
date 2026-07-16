from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import audit
from auth import get_current_user, require_role
from database import get_db
from models import Device, MaintenanceWindow, User
from schemas import MaintenanceWindowCreate, MaintenanceWindowResponse

router = APIRouter(prefix="/maintenance-windows", tags=["maintenance"])


@router.get("", response_model=List[MaintenanceWindowResponse])
def list_windows(
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(MaintenanceWindow)
    if active_only:
        now = datetime.now(timezone.utc)
        q = q.filter(MaintenanceWindow.start_at <= now, MaintenanceWindow.end_at >= now)
    return q.order_by(MaintenanceWindow.start_at.desc()).all()


@router.post("", response_model=MaintenanceWindowResponse, status_code=status.HTTP_201_CREATED)
def create_window(
    request: Request,
    body: MaintenanceWindowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("editor", "admin")),
):
    if body.end_at <= body.start_at:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="end_at must be after start_at")
    if body.device_id is not None and not db.query(Device).filter(Device.id == body.device_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    window = MaintenanceWindow(**body.model_dump())
    db.add(window)
    db.flush()  # assign id for the audit row
    audit.record(db, request, current_user, "maintenance_window.create",
                 target_type="maintenance_window", target_id=window.id,
                 summary=body.model_dump(mode="json", exclude_unset=True))
    db.commit()
    db.refresh(window)
    return window


@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_window(
    request: Request,
    window_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("editor", "admin")),
):
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Window not found")
    audit.record(db, request, current_user, "maintenance_window.delete",
                 target_type="maintenance_window", target_id=window.id,
                 summary={"device_id": window.device_id, "reason": window.reason})
    db.delete(window)
    db.commit()
