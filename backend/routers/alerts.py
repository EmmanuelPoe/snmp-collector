from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import Alert, AlertRule, AlertStatus, Device, User
from schemas import (
    AlertAssignRequest, AlertCountResponse, AlertNoteRequest, AlertResponse,
    AlertRuleCreate, AlertRuleResponse,
)

alerts_router = APIRouter(prefix="/alerts", tags=["alerts"])
rules_router = APIRouter(prefix="/alert-rules", tags=["alert-rules"])


@alerts_router.get("", response_model=List[AlertResponse])
def list_alerts(
    include_resolved: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Alert)
    if not include_resolved:
        q = q.filter(Alert.status == AlertStatus.open)
    return q.order_by(Alert.triggered_at.desc()).all()


@alerts_router.get("/count", response_model=AlertCountResponse)
def count_alerts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    count = db.query(Alert).filter(Alert.status == AlertStatus.open).count()
    return {"open": count}


@alerts_router.put("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.resolved
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


def _get_alert(alert_id: int, db: Session) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@alerts_router.put("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("editor", "admin")),
):
    alert = _get_alert(alert_id, db)
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert


@alerts_router.put("/{alert_id}/assign", response_model=AlertResponse)
def assign_alert(
    alert_id: int,
    body: AlertAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    alert = _get_alert(alert_id, db)
    if body.assigned_to is not None and not db.query(User).filter(User.id == body.assigned_to).first():
        raise HTTPException(status_code=404, detail="Assignee not found")
    alert.assigned_to = body.assigned_to
    db.commit()
    db.refresh(alert)
    return alert


@alerts_router.put("/{alert_id}/note", response_model=AlertResponse)
def set_alert_note(
    alert_id: int,
    body: AlertNoteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    alert = _get_alert(alert_id, db)
    alert.note = body.note
    db.commit()
    db.refresh(alert)
    return alert


@rules_router.get("/{device_id}", response_model=AlertRuleResponse)
def get_alert_rules(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not db.query(Device).filter(Device.id == device_id).first():
        raise HTTPException(status_code=404, detail="Device not found")
    rule = db.query(AlertRule).filter(AlertRule.device_id == device_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="No alert rules for this device")
    return rule


@rules_router.post("/{device_id}", response_model=AlertRuleResponse)
def upsert_alert_rules(
    device_id: int,
    body: AlertRuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    if not db.query(Device).filter(Device.id == device_id).first():
        raise HTTPException(status_code=404, detail="Device not found")
    rule = db.query(AlertRule).filter(AlertRule.device_id == device_id).first()
    if rule:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
    else:
        rule = AlertRule(device_id=device_id, **body.model_dump())
        db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule
