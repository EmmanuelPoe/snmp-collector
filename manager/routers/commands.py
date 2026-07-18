from typing import Optional, Union

from auth import SHARED_KEY_IDENTITY, ensure_same_agent, require_agent_auth, require_api_key
from commands import command_store
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
def fetch_commands(agent_id: str, identity: str = Depends(require_agent_auth)):
    """Agent polls this for pending commands; returned commands are marked dispatched."""
    ensure_same_agent(identity, agent_id)
    return command_store.pending_for(agent_id)


@router.post("/commands/{command_id}/result")
def post_result(command_id: str, body: CommandResult, identity: str = Depends(require_agent_auth)):
    c = command_store.get(command_id)
    if not c:
        raise HTTPException(status_code=404, detail="Command not found")
    # A command result may only come from the agent the command was issued to.
    if identity != SHARED_KEY_IDENTITY and c["agent_id"] != identity:
        raise HTTPException(status_code=403, detail="Agent credential does not match target agent")
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
    return {"command_id": c["command_id"], "status": c["status"], "result": c["result"], "error": c["error"]}
