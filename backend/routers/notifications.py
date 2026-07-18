from typing import List

import audit
from auth import get_current_user, require_role
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models import NotificationChannel, User
from schemas import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/notification-channels", tags=["notifications"])


@router.get("", response_model=List[NotificationChannelResponse])
def list_channels(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(NotificationChannel).order_by(NotificationChannel.id).all()


@router.post("", response_model=NotificationChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    request: Request,
    body: NotificationChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("editor", "admin")),
):
    channel = NotificationChannel(**body.model_dump())
    db.add(channel)
    db.flush()  # assign id for the audit row
    audit.record(
        db,
        request,
        current_user,
        "notification_channel.create",
        target_type="notification_channel",
        target_id=channel.id,
        summary=audit.redact(body.model_dump(mode="json", exclude_unset=True)),
    )
    db.commit()
    db.refresh(channel)
    return channel


@router.put("/{channel_id}", response_model=NotificationChannelResponse)
def update_channel(
    request: Request,
    channel_id: int,
    updates: NotificationChannelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("editor", "admin")),
):
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(channel, field, value)
    audit.record(
        db,
        request,
        current_user,
        "notification_channel.update",
        target_type="notification_channel",
        target_id=channel.id,
        summary=audit.redact(updates.model_dump(mode="json", exclude_unset=True)),
    )
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    request: Request,
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("editor", "admin")),
):
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    audit.record(
        db,
        request,
        current_user,
        "notification_channel.delete",
        target_type="notification_channel",
        target_id=channel.id,
        summary={"name": channel.name, "type": channel.type.value},
    )
    db.delete(channel)
    db.commit()
