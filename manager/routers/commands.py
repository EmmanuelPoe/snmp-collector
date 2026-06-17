from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Union

from auth import require_api_key
from commands import command_store

router = APIRouter(tags=["commands"])


class EnqueueCommand(BaseModel):
    type: str
    params: dict


class CommandResult(BaseModel):
    status: str  # "done" | "error"
    result: Optional[Union[list, dict]] = None
    error: Optional[str] = None


@router.post("/agents/{agent_id}/commands")
def enqueue_command(agent_id: str, body: EnqueueCommand, _: str = Depends(require_api_key)):
    cid = command_store.enqueue(agent_id, body.type, body.params)
    return {"command_id": cid}


@router.get("/agents/{agent_id}/commands")
def fetch_commands(agent_id: str, _: str = Depends(require_api_key)):
    """Agent polls this for pending commands; returned commands are marked dispatched."""
    return command_store.pending_for(agent_id)


@router.post("/commands/{command_id}/result")
def post_result(command_id: str, body: CommandResult, _: str = Depends(require_api_key)):
    try:
        command_store.complete(command_id, body.status, body.result, body.error)
    except KeyError:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"ok": True}


@router.get("/commands/{command_id}")
def get_command(command_id: str, _: str = Depends(require_api_key)):
    c = command_store.get(command_id)
    if not c:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"command_id": c["command_id"], "status": c["status"],
            "result": c["result"], "error": c["error"]}
