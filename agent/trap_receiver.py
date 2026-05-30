import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity import config as snmp_config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.hlapi import SnmpEngine

import config as agent_config

log = logging.getLogger(__name__)


async def run_trap_listener(agent_id: str, trap_buffer) -> None:
    loop = asyncio.get_event_loop()
    snmp_engine = SnmpEngine()

    snmp_config.addTransport(
        snmp_engine,
        udp.domainName,
        udp.UdpSocketTransport().openServerMode(
            ("0.0.0.0", agent_config.settings.trap_listen_port)
        ),
    )
    snmp_config.addV1System(
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
            _, transport_address = snmp_engine.msgAndPduDsp.getTransportInfo(state_ref)
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
        asyncio.run_coroutine_threadsafe(trap_buffer.add(row), loop)
        log.info("Trap received from %s oid=%s", source_ip, trap_oid)

    ntfrcv.NotificationReceiver(snmp_engine, _callback)
    snmp_engine.transportDispatcher.jobStarted(1)

    log.info(
        "Trap listener started on UDP port %d (community: %s)",
        agent_config.settings.trap_listen_port,
        agent_config.settings.trap_community,
    )

    stop_event = threading.Event()

    def _run():
        try:
            snmp_engine.transportDispatcher.runDispatcher()
        except Exception as exc:
            log.warning("Trap dispatcher error: %s", exc)
        finally:
            stop_event.set()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        snmp_engine.transportDispatcher.closeDispatcher()
        thread.join(timeout=2)
        log.info("Trap listener stopped")
        raise
