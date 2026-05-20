import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from models import RegisterRequest, RegisterResponse, HeartbeatRequest, DeviceConfig, ClaimRequest, ClaimResponse
from registry import registry, AgentInfo
from slots import slot_store
from auth import require_api_key
import config

router = APIRouter(tags=["registration"])


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest, _: str = Depends(require_api_key)):
    agent_id = registry.register(req.hostname, req.ip)
    return RegisterResponse(agent_id=agent_id, devices=await _devices_for(agent_id))


@router.post("/claim", response_model=ClaimResponse)
async def claim(req: ClaimRequest):
    try:
        agent_id = slot_store.claim(req.token, req.hostname, req.ip)
    except KeyError:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    info = AgentInfo(agent_id, req.hostname, req.ip)
    info.last_seen = datetime.now(timezone.utc)
    registry._agents[agent_id] = info
    registry._persist()
    devices = await _devices_for(agent_id)
    return ClaimResponse(agent_id=agent_id, devices=devices)


@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest, _: str = Depends(require_api_key)):
    try:
        registry.heartbeat(req.agent_id, req.pending_uploads)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent not registered")
    return {"ok": True}


@router.get("/config/{agent_id}", response_model=list[DeviceConfig])
async def get_config(agent_id: str, _: str = Depends(require_api_key)):
    if not registry.get(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return await _devices_for(agent_id)


@router.get("/agents")
def list_agents(_: str = Depends(require_api_key)):
    return _agent_list()


@router.get("/internal/agents")
def internal_list_agents():
    return _agent_list()


@router.delete("/agents", status_code=204)
def deregister_offline(_: str = Depends(require_api_key)):
    offline_ids = [a.agent_id for a in registry.all() if a.status == "offline"]
    for agent_id in offline_ids:
        registry.deregister(agent_id)


@router.delete("/agents/{agent_id}", status_code=204)
def deregister_agent(agent_id: str, _: str = Depends(require_api_key)):
    if not registry.get(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    registry.deregister(agent_id)


def _agent_list() -> list[dict]:
    agents = [
        {
            "agent_id": a.agent_id,
            "hostname": a.hostname,
            "ip": a.ip,
            "status": a.status,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None,
            "pending_uploads": a.pending_uploads,
        }
        for a in registry.all()
    ]
    pending = [
        {
            "agent_id": s.slot_id,
            "hostname": s.label,
            "ip": "",
            "status": "pending",
            "last_seen": None,
            "pending_uploads": 0,
            "slot_id": s.slot_id,
        }
        for s in slot_store.all()
    ]
    return agents + pending


async def _devices_for(agent_id: str) -> list[DeviceConfig]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{config.settings.backend_url}/internal/devices",
                params={"agent_id": agent_id},
                headers={"Authorization": f"Bearer {config.settings.manager_api_key}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            return [DeviceConfig(**d) for d in resp.json()]
        except httpx.RequestError:
            return []
