import httpx
from auth import get_current_user
from config import settings
from fastapi import APIRouter, Depends, HTTPException
from logging_json import correlation_headers
from models import User, UserRole

router = APIRouter(prefix="/agents", tags=["agents"])


def _manager_headers(auth: bool = True) -> dict:
    """Manager auth (optional) + the current correlation id, forwarded so the
    manager's logs join this request's trace (Step 5.1)."""
    headers = correlation_headers()
    if auth:
        headers["Authorization"] = f"Bearer {settings.manager_api_key}"
    return headers


@router.get("")
async def list_agents(_: User = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.manager_url}/internal/agents", headers=_manager_headers(auth=False), timeout=5.0
            )
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
                headers=_manager_headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Manager unavailable")


@router.delete("", status_code=204)
async def deregister_offline_agents(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.delete(
                f"{settings.manager_url}/agents",
                headers=_manager_headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
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
                headers=_manager_headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Manager unavailable")
