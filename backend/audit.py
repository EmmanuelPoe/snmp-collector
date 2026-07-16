"""Audit logging helpers (Step 1.5 / plan Step 17).

record() queues an AuditLog row in the caller's session so it commits
atomically with the change being audited. Every mutating router calls it;
GET endpoints are not audited (exports will be, in plan Step 40).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models import AuditLog, User

logger = logging.getLogger(__name__)

# Fields whose values must never appear in an audit summary. The field *name*
# still shows up, so "a credential was changed" stays visible without leaking
# the value. "url" covers notification webhook URLs, which embed secrets.
REDACTED_FIELDS = {
    "snmp_community", "auth_password", "priv_password",
    "password", "current_password", "new_password", "hashed_password",
    "url",
}
REDACTED = "[REDACTED]"


def redact(fields: dict) -> dict:
    return {k: (REDACTED if k in REDACTED_FIELDS else v) for k, v in fields.items()}


def _source_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    # nginx sets X-Real-IP; fall back to the direct peer address.
    return request.headers.get("X-Real-IP") or (request.client.host if request.client else None)


def record(
    db: Session,
    request: Optional[Request],
    actor: Optional[User],
    action: str,
    *,
    target_type: Optional[str] = None,
    target_id=None,
    summary: Optional[dict] = None,
    actor_email: Optional[str] = None,
) -> None:
    """Add an audit row to the caller's transaction; the caller's commit
    persists it. actor=None with actor_email set records an unauthenticated
    attempt (e.g. failed login)."""
    db.add(AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else actor_email,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        summary=summary,
        source_ip=_source_ip(request),
    ))


def prune_old_entries(db: Session, retention_days: int) -> int:
    """Delete audit rows older than the retention window. Returns rows deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete()
    db.commit()
    return deleted
