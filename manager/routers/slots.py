from fastapi import APIRouter, Depends
from models import SlotCreateRequest, SlotResponse
from slots import slot_store
from auth import require_api_key
import config

router = APIRouter(tags=["slots"])


@router.post("/slots", response_model=SlotResponse)
def create_slot(req: SlotCreateRequest, _: str = Depends(require_api_key)):
    slot = slot_store.create(req.label)
    install_cmd = (
        f"docker run -d --name snmp-agent \\\n"
        f"  -v snmp-agent-data:/data \\\n"
        f"  -e MANAGER_URL={config.settings.manager_public_url} \\\n"
        f"  -e MANAGER_API_KEY=<your-manager-api-key> \\\n"
        f"  -e CLAIM_TOKEN={slot.token} \\\n"
        f"  snmp-collector-agent:latest"
    )
    return SlotResponse(
        slot_id=slot.slot_id,
        label=slot.label,
        token=slot.token,
        expires_at=slot.expires_at,
        install_command=install_cmd,
    )


@router.delete("/slots/{slot_id}", status_code=204)
def delete_slot(slot_id: str, _: str = Depends(require_api_key)):
    slot_store.delete(slot_id)
