from fastapi import APIRouter, Depends, HTTPException
from auth import require_api_key

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
async def list_devices(_: str = Depends(require_api_key)):
    raise HTTPException(status_code=501, detail="Device inventory is managed by the backend service")


@router.post("", status_code=201)
async def add_device(_: str = Depends(require_api_key)):
    raise HTTPException(status_code=501, detail="Device inventory is managed by the backend service")


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, _: str = Depends(require_api_key)):
    raise HTTPException(status_code=501, detail="Device inventory is managed by the backend service")
