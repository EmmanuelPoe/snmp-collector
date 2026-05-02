import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
import config


class AgentInfo:
    def __init__(self, agent_id: str, hostname: str, ip: str):
        self.agent_id = agent_id
        self.hostname = hostname
        self.ip = ip
        self.last_seen: datetime | None = None
        self.pending_uploads: int = 0
        self.registered_at = datetime.now(timezone.utc)

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
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "pending_uploads": self.pending_uploads,
            "registered_at": self.registered_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentInfo":
        agent = cls(d["agent_id"], d["hostname"], d["ip"])
        if d.get("last_seen"):
            agent.last_seen = datetime.fromisoformat(d["last_seen"])
        agent.pending_uploads = d.get("pending_uploads", 0)
        agent.registered_at = datetime.fromisoformat(
            d.get("registered_at", datetime.now(timezone.utc).isoformat())
        )
        return agent


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentInfo] = {}
        self._load()

    def register(self, hostname: str, ip: str) -> str:
        agent_id = f"{hostname}-{uuid.uuid4().hex[:8]}"
        info = AgentInfo(agent_id, hostname, ip)
        info.last_seen = datetime.now(timezone.utc)
        self._agents[agent_id] = info
        self._persist()
        return agent_id

    def heartbeat(self, agent_id: str, pending_uploads: int = 0) -> None:
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not registered")
        self._agents[agent_id].last_seen = datetime.now(timezone.utc)
        self._agents[agent_id].pending_uploads = pending_uploads
        self._persist()

    def get(self, agent_id: str) -> AgentInfo | None:
        return self._agents.get(agent_id)

    def all(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def deregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
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
        except (json.JSONDecodeError, KeyError, ValueError):
            pass


registry = AgentRegistry()
