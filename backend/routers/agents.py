from fastapi import APIRouter, Depends, HTTPException
import httpx

from auth import get_current_user
from config import settings
from models import User

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(_: User = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{settings.manager_url}/internal/agents", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Manager unavailable")
