import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config

logger = logging.getLogger(__name__)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_secret() -> str:
    """Per-agent credential (Step 1.7), returned to the agent exactly once at
    register/claim; only its hash is stored."""
    return secrets.token_urlsafe(32)


class AgentInfo:
    def __init__(self, agent_id: str, hostname: str, ip: str, secret_hash: str | None = None):
        self.agent_id = agent_id
        self.hostname = hostname
        self.ip = ip
        self.secret_hash = secret_hash
        self.last_seen: datetime | None = None
        self.pending_uploads: int = 0
        self.registered_at = datetime.now(timezone.utc)

    def verify_secret(self, secret: str) -> bool:
        return bool(self.secret_hash) and hmac.compare_digest(self.secret_hash, hash_secret(secret))

    @property
    def status(self) -> str:
        if self.last_seen is None:
            return "offline"
        age = (datetime.now(timezone.utc) - self.last_seen).total_seconds()
        if age < 90:
            return "online"
        if age < 300:
            return "degraded"
        return "offline"

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "hostname": self.hostname,
            "ip": self.ip,
            "secret_hash": self.secret_hash,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "pending_uploads": self.pending_uploads,
            "registered_at": self.registered_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentInfo":
        # Pre-Step-1.7 registry rows have no secret_hash — those agents can only
        # authenticate with the shared key (grace mode) until re-enrolled.
        agent = cls(d["agent_id"], d["hostname"], d["ip"], secret_hash=d.get("secret_hash"))
        if d.get("last_seen"):
            agent.last_seen = datetime.fromisoformat(d["last_seen"])
        agent.pending_uploads = d.get("pending_uploads", 0)
        agent.registered_at = datetime.fromisoformat(d.get("registered_at", datetime.now(timezone.utc).isoformat()))
        return agent


class AgentRegistry:
    """File-backed registry (dev default; unit tests need no DB). The in-memory
    dict is authoritative for reads; subclasses override the persistence hooks
    (_save_agent/_delete_agent/_load) for other backends."""

    def __init__(self):
        self._agents: dict[str, AgentInfo] = {}
        self._load()

    def register(self, hostname: str, ip: str) -> tuple[str, str]:
        """Returns (agent_id, secret). The secret is not stored — hand it to the
        agent now or lose it."""
        agent_id = f"{hostname}-{uuid.uuid4().hex[:8]}"
        secret = new_secret()
        info = AgentInfo(agent_id, hostname, ip, secret_hash=hash_secret(secret))
        info.last_seen = datetime.now(timezone.utc)
        self._agents[agent_id] = info
        self._save_agent(info)
        return agent_id, secret

    def add(self, info: AgentInfo) -> None:
        self._agents[info.agent_id] = info
        self._save_agent(info)

    def heartbeat(self, agent_id: str, pending_uploads: int = 0) -> None:
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not registered")
        info = self._agents[agent_id]
        info.last_seen = datetime.now(timezone.utc)
        info.pending_uploads = pending_uploads
        self._save_agent(info)

    def get(self, agent_id: str) -> AgentInfo | None:
        return self._agents.get(agent_id)

    def all(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def deregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._delete_agent(agent_id)

    # -- persistence hooks -------------------------------------------------

    def _save_agent(self, info: AgentInfo) -> None:
        self._persist()

    def _delete_agent(self, agent_id: str) -> None:
        self._persist()

    def _persist(self) -> None:
        path = Path(config.settings.registry_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps([a.to_dict() for a in self._agents.values()], indent=2))
        os.replace(tmp, path)

    def _load(self) -> None:
        path = Path(config.settings.registry_path)
        if not path.exists():
            return
        try:
            for d in json.loads(path.read_text()):
                agent = AgentInfo.from_dict(d)
                self._agents[agent.agent_id] = agent
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            # Step 2.2: a corrupt registry is quarantined, not silently
            # discarded — operators can inspect/restore it.
            quarantine = path.with_suffix(".corrupt")
            logger.error("registry file %s is corrupt (%s) — quarantined to %s, starting empty", path, exc, quarantine)
            os.replace(path, quarantine)
            self._agents.clear()


class DbAgentRegistry(AgentRegistry):
    """Postgres-backed registry (Step 2.1 / plan Step 25). Schema is owned by
    backend Alembic (migration 025 `agent_registry`); the DATA is owned here —
    the documented mirror of the DuckDB arrangement. SQLAlchemy Core only, so
    tests can point database_url at SQLite.

    Persistence errors are logged, never raised: the in-memory cache stays
    authoritative and the next heartbeat retries the write."""

    def __init__(self, database_url: str | None = None):
        from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine

        url = database_url or config.settings.database_url
        if not url:
            raise RuntimeError("REGISTRY_BACKEND=postgres requires DATABASE_URL to be set")
        self._engine = create_engine(url, pool_pre_ping=True)
        # Must match backend/alembic/versions/025_agent_registry.py.
        self._table = Table(
            "agent_registry",
            MetaData(),
            Column("agent_id", String(255), primary_key=True),
            Column("hostname", String(255), nullable=False),
            Column("ip", String(45), nullable=False),
            Column("last_seen", DateTime(timezone=True), nullable=True),
            Column("pending_uploads", Integer, nullable=False, default=0),
            Column("credential_hash", String(64), nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=True),
        )
        super().__init__()

    def _save_agent(self, info: AgentInfo) -> None:
        values = {
            "hostname": info.hostname,
            "ip": info.ip,
            "last_seen": info.last_seen,
            "pending_uploads": info.pending_uploads,
            "credential_hash": info.secret_hash,
            "created_at": info.registered_at,
        }
        try:
            with self._engine.begin() as conn:
                # Portable upsert (works on Postgres and the SQLite test URL).
                updated = conn.execute(
                    self._table.update().where(self._table.c.agent_id == info.agent_id).values(**values)
                )
                if updated.rowcount == 0:
                    conn.execute(self._table.insert().values(agent_id=info.agent_id, **values))
        except Exception as exc:
            logger.warning("registry DB write failed for %s: %s", info.agent_id, exc)

    def _delete_agent(self, agent_id: str) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(self._table.delete().where(self._table.c.agent_id == agent_id))
        except Exception as exc:
            logger.warning("registry DB delete failed for %s: %s", agent_id, exc)

    def _load(self) -> None:
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(self._table.select()).mappings().all()
        except Exception as exc:
            logger.warning(
                "registry DB load failed (%s) — starting empty; agents repopulate via heartbeat/re-enroll", exc
            )
            return
        for row in rows:
            info = AgentInfo(row["agent_id"], row["hostname"], row["ip"], secret_hash=row["credential_hash"])
            info.last_seen = _as_utc(row["last_seen"])
            info.pending_uploads = row["pending_uploads"] or 0
            if row["created_at"] is not None:
                info.registered_at = _as_utc(row["created_at"])
            self._agents[info.agent_id] = info


def _as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes for DateTime(timezone=True); Postgres aware."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _make_registry() -> AgentRegistry:
    if config.settings.registry_backend == "postgres":
        return DbAgentRegistry()
    return AgentRegistry()


registry = _make_registry()
