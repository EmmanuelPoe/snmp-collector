from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from models import AuditLog, User

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEntryResponse(BaseModel):
    id: int
    actor_user_id: Optional[int]
    actor_email: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    summary: Optional[Any]
    source_ip: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class AuditPageResponse(BaseModel):
    total: int
    items: List[AuditEntryResponse]


@router.get("", response_model=AuditPageResponse)
def list_audit_entries(
    actor_email: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Read-only audit trail (admin). The table is append-only — no write
    routes exist for it."""
    q = db.query(AuditLog)
    if actor_email:
        q = q.filter(AuditLog.actor_email == actor_email)
    if action:
        q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    if target_id:
        q = q.filter(AuditLog.target_id == target_id)
    if start:
        q = q.filter(AuditLog.created_at >= start)
    if end:
        q = q.filter(AuditLog.created_at <= end)
    total = q.count()
    items = (q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
             .offset(offset).limit(limit).all())
    return {"total": total, "items": items}
