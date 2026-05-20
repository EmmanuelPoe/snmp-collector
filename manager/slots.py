import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import config

log = logging.getLogger(__name__)


class Slot:
    def __init__(self, slot_id: str, label: str, token: str, expires_at: datetime):
        self.slot_id = slot_id
        self.label = label
        self.token = token
        self.status = "pending"
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "label": self.label,
            "token": self.token,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Slot":
        def _parse_dt(s: str) -> datetime:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        slot = cls(
            slot_id=d["slot_id"],
            label=d["label"],
            token=d["token"],
            expires_at=_parse_dt(d["expires_at"]),
        )
        slot.status = d["status"]
        slot.created_at = _parse_dt(d["created_at"])
        return slot


class SlotStore:
    def __init__(self):
        self._slots: dict[str, Slot] = {}
        self._load()

    def create(self, label: str) -> Slot:
        self._cleanup_expired()
        slot = Slot(
            slot_id=str(uuid.uuid4()),
            label=label,
            token=secrets.token_hex(16),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=config.settings.slot_expiry_hours),
        )
        self._slots[slot.slot_id] = slot
        self._persist()
        return slot

    def get_by_token(self, token: str) -> Slot | None:
        self._cleanup_expired()
        return next((s for s in self._slots.values() if s.token == token), None)

    def claim(self, token: str, hostname: str, ip: str) -> str:
        slot = self.get_by_token(token)
        if slot is None:
            raise KeyError("Token not found or expired")
        safe_label = slot.label.lower().replace(" ", "-")
        agent_id = f"{safe_label}-{slot.token[:8]}"
        del self._slots[slot.slot_id]
        self._persist()
        return agent_id

    def all(self) -> list[Slot]:
        self._cleanup_expired()
        return list(self._slots.values())

    def delete(self, slot_id: str) -> None:
        self._slots.pop(slot_id, None)
        self._persist()

    def _cleanup_expired(self) -> None:
        expired = [sid for sid, s in self._slots.items() if s.is_expired()]
        for sid in expired:
            del self._slots[sid]
        if expired:
            self._persist()

    def _persist(self) -> None:
        path = Path(config.settings.slots_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps([s.to_dict() for s in self._slots.values()], indent=2))
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _load(self) -> None:
        path = Path(config.settings.slots_path)
        if not path.exists():
            return
        try:
            for d in json.loads(path.read_text()):
                slot = Slot.from_dict(d)
                if not slot.is_expired():
                    self._slots[slot.slot_id] = slot
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            log.warning("Failed to load slots from %s: %s", path, exc)


slot_store = SlotStore()
