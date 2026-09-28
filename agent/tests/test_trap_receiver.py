"""Trap-path coverage for the pysnmp 7 receiver.

The compose default is TRAP_ENABLED=false and `make simulation` never sends a
trap, so this path had no automated coverage at all — which mattered when the
pysnmp 4 -> 7 migration rewrote it (asyncore dispatcher thread -> asyncio
dispatcher on the running loop). This binds the real receiver on a loopback
port, sends a real v2c trap at it, and asserts the decoded row.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

TRAP_PORT = 16211
COMMUNITY = "public"
# snmpTrapOID.0 -> linkDown, plus sysUpTime.0 as a payload varbind.
LINK_DOWN = "1.3.6.1.6.3.1.1.5.3"
SYSUPTIME = "1.3.6.1.2.1.1.3.0"


class _FakeBuffer:
    """Stands in for the agent's TrapBuffer — only `add` is used."""

    def __init__(self):
        self.rows = []

    async def add(self, row):
        self.rows.append(row)


async def _send_trap(port):
    from pysnmp.hlapi.v3arch.asyncio import (
        CommunityData,
        ContextData,
        NotificationType,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        send_notification,
    )

    err_ind, _, _, _ = await send_notification(
        SnmpEngine(),
        CommunityData(COMMUNITY, mpModel=1),  # mpModel=1 -> SNMPv2c
        await UdpTransportTarget.create(("127.0.0.1", port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity(LINK_DOWN)).add_varbinds(ObjectType(ObjectIdentity(SYSUPTIME), 4242)),
    )
    return err_ind


@pytest.mark.asyncio
async def test_trap_listener_receives_and_buffers_a_v2c_trap(monkeypatch):
    monkeypatch.setenv("MANAGER_URL", "http://manager:8000")
    import config as agent_config

    monkeypatch.setattr(agent_config.settings, "trap_listen_port", TRAP_PORT)
    monkeypatch.setattr(agent_config.settings, "trap_community", COMMUNITY)

    from trap_receiver import run_trap_listener

    buffer = _FakeBuffer()
    listener = asyncio.create_task(run_trap_listener("ag-test-01", buffer))
    await asyncio.sleep(0.4)  # let open_server_mode bind

    try:
        assert await _send_trap(TRAP_PORT) is None, "trap send reported an error"
        for _ in range(40):
            if buffer.rows:
                break
            await asyncio.sleep(0.1)
    finally:
        listener.cancel()
        with pytest.raises(asyncio.CancelledError):
            await listener

    assert buffer.rows, "no trap reached the buffer"
    row = buffer.rows[0]
    assert row["agent_id"] == "ag-test-01"
    # Resolved from the transport, not the payload — this is what regressed
    # between pysnmp versions (msgAndPduDsp -> message_dispatcher).
    assert row["device_ip"] == "127.0.0.1"
    varbinds = json.loads(row["varbinds"])
    assert varbinds[SYSUPTIME] == "4242"
    assert varbinds["1.3.6.1.6.3.1.1.4.1.0"] == LINK_DOWN
    assert row["received_at"]
