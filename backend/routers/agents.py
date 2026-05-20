from fastapi import APIRouter, Depends, HTTPException
import httpx

from auth import get_current_user
from config import settings
from models import User, UserRole

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


@router.post("/slots")
async def create_slot(body: dict, current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{settings.manager_url}/slots",
                json=body,
                headers={"Authorization": f"Bearer {settings.manager_api_key}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Manager unavailable")


@router.delete("/slots/{slot_id}", status_code=204)
async def delete_slot(slot_id: str, current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.delete(
                f"{settings.manager_url}/slots/{slot_id}",
                headers={"Authorization": f"Bearer {settings.manager_api_key}"},
                timeout=5.0,
            )
            resp.raise_for_status()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Manager unavailable")
