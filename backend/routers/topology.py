import time
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from config import settings
from database import get_db
from models import Device, TopologyEdge, Alert, AlertType, AlertStatus, User
from routers.devices import _resolve_agent_id, _manager_headers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/topology", tags=["topology"])

# Total wall-clock budget for one discovery run (agents poll for commands every
# 5s, so a device's LLDP walk lands within ~5-10s of enqueue).
_DISCOVER_TIMEOUT_S = 30
_POLL_INTERVAL_S = 2


def _device_creds(device: Device) -> dict:
    return {
        "id": str(device.id),
        "ip": device.ip_address,
        "snmp_version": device.snmp_version,
        "snmp_community": device.snmp_community,
        "snmp_port": device.snmp_port,
        "username": device.username,
        "auth_protocol": device.auth_protocol,
        "auth_password": device.auth_password,
        "priv_protocol": device.priv_protocol,
        "priv_password": device.priv_password,
    }


def _build_resolver(devices: list[Device]) -> dict:
    """Map lowercased sysname / IP -> device id, for matching LLDP neighbours to
    known devices."""
    resolver: dict = {}
    for d in devices:
        if d.name:
            resolver[d.name.lower()] = d.id
        if d.ip_address:
            resolver[d.ip_address.lower()] = d.id
    return resolver


def _resolve_neighbour(neighbour: dict, resolver: dict) -> int | None:
    sysname = (neighbour.get("remote_sysname") or "").strip().lower()
    if sysname and sysname in resolver:
        return resolver[sysname]
    # Some devices report a bare hostname; match on the first label too.
    if sysname and "." in sysname:
        short = sysname.split(".", 1)[0]
        if short in resolver:
            return resolver[short]
    return None


@router.post("/discover")
def discover_topology(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor", "admin")),
):
    """Walk LLDP on every enabled device via the agent command channel, then
    rebuild the topology edge set. Blocking, bounded by _DISCOVER_TIMEOUT_S."""
    devices = db.query(Device).filter(Device.enabled == True).all()
    resolver = _build_resolver(devices)

    pending: dict[str, Device] = {}
    no_agent = 0
    for d in devices:
        agent_id = _resolve_agent_id(d)
        if not agent_id:
            no_agent += 1
            continue
        try:
            resp = httpx.post(
                f"{settings.manager_url}/agents/{agent_id}/commands",
                json={"type": "lldp", "params": {"device": _device_creds(d)}},
                headers=_manager_headers(), timeout=10,
            )
            resp.raise_for_status()
            pending[resp.json()["command_id"]] = d
        except httpx.HTTPError as exc:
            logger.warning("LLDP enqueue failed for device %s: %s", d.id, exc)

    results: dict[int, list] = {}
    deadline = time.time() + _DISCOVER_TIMEOUT_S
    while pending and time.time() < deadline:
        time.sleep(_POLL_INTERVAL_S)
        for cid in list(pending):
            try:
                r = httpx.get(f"{settings.manager_url}/commands/{cid}",
                              headers=_manager_headers(), timeout=10).json()
            except httpx.HTTPError:
                continue
            if r.get("status") in ("done", "error"):
                d = pending.pop(cid)
                if r.get("status") == "done":
                    results[d.id] = r.get("result") or []

    edge_count = 0
    for device_id, neighbours in results.items():
        # Full re-walk replaces this device's adjacency.
        db.query(TopologyEdge).filter(TopologyEdge.local_device_id == device_id).delete()
        for n in neighbours:
            db.add(TopologyEdge(
                local_device_id=device_id,
                local_port=n.get("local_port_desc") or n.get("local_port_num"),
                remote_chassis_id=n.get("remote_chassis_id"),
                remote_sysname=n.get("remote_sysname"),
                remote_port_id=n.get("remote_port_id"),
                remote_port_desc=n.get("remote_port_desc"),
                remote_device_id=_resolve_neighbour(n, resolver),
            ))
            edge_count += 1
    db.commit()

    return {
        "devices_walked": len(results),
        "devices_no_agent": no_agent,
        "timed_out": len(pending),
        "edges": edge_count,
    }


@router.get("/graph")
def topology_graph(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Nodes (devices) + resolved edges + unresolved external neighbours, for the
    topology map. Node status is derived from open device_unreachable alerts."""
    devices = db.query(Device).all()
    down_ids = {
        a.device_id for a in db.query(Alert).filter(
            Alert.alert_type == AlertType.device_unreachable,
            Alert.status == AlertStatus.open,
            Alert.device_id.isnot(None),
        ).all()
    }
    nodes = [{
        "id": d.id,
        "name": d.name,
        "ip": d.ip_address,
        "type": d.device_type,
        "tags": d.tags or [],
        "status": "down" if d.id in down_ids else "up",
    } for d in devices]

    edges, unresolved = [], []
    for e in db.query(TopologyEdge).all():
        if e.remote_device_id is not None:
            edges.append({
                "id": e.id,
                "source": e.local_device_id,
                "target": e.remote_device_id,
                "local_port": e.local_port,
                "remote_port": e.remote_port_desc or e.remote_port_id,
            })
        else:
            unresolved.append({
                "id": e.id,
                "local_device_id": e.local_device_id,
                "local_port": e.local_port,
                "remote_sysname": e.remote_sysname,
                "remote_chassis_id": e.remote_chassis_id,
                "remote_port": e.remote_port_desc or e.remote_port_id,
            })

    return {"nodes": nodes, "edges": edges, "unresolved": unresolved}
