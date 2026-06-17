"""In-memory command channel for agent request/response (e.g. on-demand SNMP
walks for the MIB browser). Agents are outbound-only, so they poll for pending
commands and post results back. Commands are transient — held in memory with a
short TTL, never persisted."""
import time
import uuid
from threading import Lock

_TTL_SECONDS = 300


class CommandStore:
    def __init__(self):
        self._commands: dict[str, dict] = {}
        self._lock = Lock()

    def _expire(self):
        now = time.monotonic()
        stale = [cid for cid, c in self._commands.items() if now - c["created_at"] > _TTL_SECONDS]
        for cid in stale:
            del self._commands[cid]

    def enqueue(self, agent_id: str, type_: str, params: dict) -> str:
        cid = uuid.uuid4().hex
        with self._lock:
            self._expire()
            self._commands[cid] = {
                "command_id": cid, "agent_id": agent_id, "type": type_,
                "params": params, "status": "pending", "result": None,
                "error": None, "created_at": time.monotonic(),
            }
        return cid

    def pending_for(self, agent_id: str) -> list:
        with self._lock:
            self._expire()
            out = []
            for c in self._commands.values():
                if c["agent_id"] == agent_id and c["status"] == "pending":
                    c["status"] = "dispatched"
                    out.append({"command_id": c["command_id"], "type": c["type"], "params": c["params"]})
            return out

    def complete(self, command_id: str, status: str, result=None, error=None):
        with self._lock:
            c = self._commands.get(command_id)
            if not c:
                raise KeyError(command_id)
            c["status"] = status
            c["result"] = result
            c["error"] = error

    def get(self, command_id: str):
        with self._lock:
            self._expire()
            return self._commands.get(command_id)


command_store = CommandStore()
