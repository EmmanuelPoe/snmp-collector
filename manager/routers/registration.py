import httpx
from fastapi import APIRouter, Depends, HTTPException
from models import RegisterRequest, RegisterResponse, HeartbeatRequest, DeviceConfig
from registry import registry
from auth import require_api_key
import config

router = APIRouter(tags=["registration"])


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest, _: str = Depends(require_api_key)):
    agent_id = registry.register(req.hostname, req.ip)
    return RegisterResponse(agent_id=agent_id, devices=await _devices_for(agent_id))


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


@router.delete("/agents/{agent_id}", status_code=204)
def deregister_agent(agent_id: str, _: str = Depends(require_api_key)):
    if not registry.get(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    registry.deregister(agent_id)


def _agent_list() -> list[dict]:
    return [
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
