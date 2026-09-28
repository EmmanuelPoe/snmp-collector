import asyncio
import json
import logging
from datetime import datetime, timezone

import config as agent_config
import pysnmp.carrier.asyncio.dgram.udp as udp
from pysnmp.entity import config as snmp_config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

log = logging.getLogger(__name__)


async def run_trap_listener(agent_id: str, trap_buffer) -> None:
    loop = asyncio.get_running_loop()
    snmp_engine = SnmpEngine()

    snmp_config.add_transport(
        snmp_engine,
        udp.DOMAIN_NAME,
        udp.UdpTransport().open_server_mode(("0.0.0.0", agent_config.settings.trap_listen_port)),
    )
    snmp_config.add_v1_system(
        snmp_engine,
        "trap-community",
        agent_config.settings.trap_community,
    )

    def _callback(snmp_engine, state_ref, ctx_engine_id, ctx_name, var_binds, cb_ctx):
        now = datetime.now(timezone.utc).isoformat()
        trap_oid = None
        varbinds = {}
        for oid, val in var_binds:
            oid_str = str(oid)
            if trap_oid is None:
                trap_oid = oid_str
            varbinds[oid_str] = str(val)

        try:
            _, transport_address = snmp_engine.message_dispatcher.get_transport_info(state_ref)
            source_ip = str(transport_address[0])
        except Exception:
            source_ip = "unknown"

        row = {
            "agent_id": agent_id,
            "device_ip": source_ip,
            "trap_oid": trap_oid or "unknown",
            "varbinds": json.dumps(varbinds),
            "received_at": now,
        }
        # pysnmp 7's AsyncioDispatcher invokes this on the event loop, so the
        # buffer write is a plain task. pysnmp 4 needed run_coroutine_threadsafe
        # because its asyncore dispatcher ran in a separate thread.
        loop.create_task(trap_buffer.add(row))
        log.info("Trap received from %s oid=%s", source_ip, trap_oid)

    ntfrcv.NotificationReceiver(snmp_engine, _callback)
    # Hold a job open so the dispatcher does not consider itself finished and
    # tear the transport down.
    snmp_engine.transport_dispatcher.job_started(1)

    log.info(
        "Trap listener started on UDP port %d (community: %s)",
        agent_config.settings.trap_listen_port,
        agent_config.settings.trap_community,
    )

    try:
        # open_server_mode registered the datagram endpoint on this loop, so
        # datagrams arrive without a blocking run_dispatcher() call (pysnmp 4
        # needed one, in a thread). Just stay alive until cancelled.
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        snmp_engine.transport_dispatcher.close_dispatcher()
        log.info("Trap listener stopped")
        raise
