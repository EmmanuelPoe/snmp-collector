from fastapi import APIRouter, HTTPException
import httpx
from config import settings

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{settings.manager_url}/internal/agents", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Manager unavailable")
