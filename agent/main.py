import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import config
import credentials
import httpx
from models import DeviceConfig
from snmp import walk_device, walk_lldp, walk_oid
from trap_receiver import run_trap_listener
from uploader import TrapBuffer, UploadBuffer


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "service": "agent",
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
log = logging.getLogger(__name__)

_agent_id: str | None = None
_agent_secret: str | None = None
_buffer: UploadBuffer | None = None
_trap_buffer: TrapBuffer | None = None
_reregister_lock = asyncio.Lock()


def _auth_token() -> str:
    return credentials.auth_token(_agent_id, _agent_secret)


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_auth_token()}"}


async def _register() -> tuple[str, str | None]:
    id_file = Path(config.settings.agent_id_path)

    if id_file.exists():
        stored = id_file.read_text().strip()
        secret = credentials.load_secret()
        if secret is None:
            log.warning(
                "No stored agent secret — falling back to the shared key (re-enroll for a per-agent credential)"
            )
        log.info("Reusing stored agent_id: %s", stored)
        return stored, secret

    if config.settings.claim_token:
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{config.settings.manager_url}/claim",
                        json={
                            "token": config.settings.claim_token,
                            "hostname": config.settings.agent_hostname,
                            "ip": config.settings.agent_ip,
                        },
                        timeout=10.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    agent_id, secret = data["agent_id"], data.get("agent_secret")
                    id_file.parent.mkdir(parents=True, exist_ok=True)
                    id_file.write_text(agent_id)
                    if secret:
                        credentials.save_secret(secret)
                    log.info("Claimed slot, registered as agent_id: %s", agent_id)
                    return agent_id, secret
            except Exception as exc:
                log.warning("Claim failed: %s — retrying in 10s", exc)
                await asyncio.sleep(10)

    while True:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{config.settings.manager_url}/register",
                    json={"hostname": config.settings.agent_hostname, "ip": config.settings.agent_ip},
                    headers={"Authorization": f"Bearer {config.settings.manager_api_key}"},
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                agent_id, secret = data["agent_id"], data.get("agent_secret")
                id_file.parent.mkdir(parents=True, exist_ok=True)
                id_file.write_text(agent_id)
                if secret:
                    credentials.save_secret(secret)
                log.info("Registered as agent_id: %s", agent_id)
                return agent_id, secret
        except Exception as exc:
            log.warning("Registration failed: %s — retrying in 10s", exc)
            await asyncio.sleep(10)


async def _reregister(stale_id: str) -> None:
    """Recover when the manager returns 404 for us — it no longer knows this
    agent because its registry was reset, migrated, or restored from a backup
    older than our enrollment. Drop the stored identity, register fresh, and
    re-point the upload buffers at the new id+token. Concurrent callers (the
    heartbeat and poll loops can both see the 404) collapse to a single
    re-registration via the lock + stale-id guard.

    Note: an agent enrolled with a one-time claim token cannot self-heal once
    that token is consumed — it will retry registration until re-enrolled.
    """
    global _agent_id, _agent_secret
    async with _reregister_lock:
        if _agent_id != stale_id:
            return  # another loop already healed us
        log.warning("Manager does not recognise agent_id %s — re-registering", stale_id)
        Path(config.settings.agent_id_path).unlink(missing_ok=True)
        credentials.clear_secret()
        _agent_id, _agent_secret = await _register()
        token = _auth_token()
        if _buffer:
            _buffer.update_identity(_agent_id, token)
        if _trap_buffer:
            _trap_buffer.update_identity(_agent_id, token)
        log.info("Re-registered as agent_id: %s", _agent_id)


# Touched every heartbeat cycle; the compose healthcheck asserts freshness
# (Step 2.3 — liveness of the asyncio loops, not manager reachability).
LIVENESS_FILE = Path("/tmp/agent-alive")


def _touch_liveness() -> None:
    try:
        LIVENESS_FILE.touch()
    except OSError:
        pass


async def _heartbeat_loop() -> None:
    _touch_liveness()
    while True:
        await asyncio.sleep(30)
        _touch_liveness()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{config.settings.manager_url}/heartbeat",
                    json={"agent_id": _agent_id, "pending_uploads": _buffer.pending_count() if _buffer else 0},
                    headers=_auth_headers(),
                    timeout=5.0,
                )
            if resp.status_code == 404:
                await _reregister(_agent_id)
        except Exception as exc:
            log.debug("Heartbeat failed: %s", exc)


async def _fetch_devices() -> list[DeviceConfig]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{config.settings.manager_url}/config/{_agent_id}",
            headers=_auth_headers(),
            timeout=10.0,
        )
        resp.raise_for_status()
        return [DeviceConfig(**d) for d in resp.json()]


async def _poll_device(device: DeviceConfig) -> None:
    log.info("Polling %s (%s)", device.ip, device.snmp_version)
    try:
        rows = await asyncio.to_thread(walk_device, device)
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            row["agent_id"] = _agent_id
            row["device_ip"] = device.ip
            row["collected_at"] = now
            await _buffer.add_and_maybe_flush(row)
        log.info("Polled %s: %d rows", device.ip, len(rows))
    except Exception as exc:
        log.warning("Poll failed for %s: %s", device.ip, exc)


async def _poll_loop() -> None:
    while True:
        try:
            devices = await _fetch_devices()
        except Exception as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
                await _reregister(_agent_id)
                continue
            log.warning("Failed to fetch devices: %s — retrying in 60s", exc)
            await asyncio.sleep(60)
            continue

        tasks = [_poll_device(d) for d in devices]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(config.settings.poll_interval_seconds)


async def _retry_loop() -> None:
    while True:
        await asyncio.sleep(60)
        await _buffer.flush_retry_queue()
        await _buffer.tick()
        if _trap_buffer:
            await _trap_buffer.flush()


async def _post_command_result(client, command_id, status, result=None, error=None):
    try:
        await client.post(
            f"{config.settings.manager_url}/commands/{command_id}/result",
            json={"status": status, "result": result, "error": error},
            headers=_auth_headers(),
            timeout=10.0,
        )
    except Exception as exc:
        log.warning("Failed to post command result %s: %s", command_id, exc)


async def _execute_command(client, cmd) -> None:
    command_id = cmd.get("command_id")
    ctype = cmd.get("type")
    if ctype not in ("walk", "lldp"):
        await _post_command_result(client, command_id, "error", error=f"unknown command type: {ctype}")
        return
    params = cmd.get("params") or {}
    try:
        device = DeviceConfig(**params["device"])
        if ctype == "walk":
            base_oid = params.get("base_oid", "1.3.6.1.2.1")
            max_rows = params.get("max_rows", 500)
            rows = await asyncio.to_thread(walk_oid, device, base_oid, max_rows)
            log.info("Walk command %s: %d OIDs from %s", command_id, len(rows), device.ip)
        else:  # lldp
            rows = await asyncio.to_thread(walk_lldp, device)
            log.info("LLDP command %s: %d neighbours from %s", command_id, len(rows), device.ip)
        await _post_command_result(client, command_id, "done", result=rows)
    except Exception as exc:
        await _post_command_result(client, command_id, "error", error=str(exc))
        log.warning("Command %s (%s) failed: %s", command_id, ctype, exc)


async def _command_loop() -> None:
    while True:
        await asyncio.sleep(5)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{config.settings.manager_url}/agents/{_agent_id}/commands",
                    headers=_auth_headers(),
                    timeout=10.0,
                )
                resp.raise_for_status()
                commands = resp.json()
                for cmd in commands:
                    await _execute_command(client, cmd)
        except Exception as exc:
            log.debug("Command poll failed: %s", exc)


async def _trap_loop() -> None:
    await run_trap_listener(_agent_id, _trap_buffer)


async def main() -> None:
    global _agent_id, _agent_secret, _buffer, _trap_buffer
    _agent_id, _agent_secret = await _register()
    _buffer = UploadBuffer(agent_id=_agent_id, token=_auth_token())

    loops = [
        _heartbeat_loop(),
        _poll_loop(),
        _retry_loop(),
        _command_loop(),
    ]

    if config.settings.trap_enabled:
        _trap_buffer = TrapBuffer(agent_id=_agent_id, token=_auth_token())
        loops.append(_trap_loop())
        log.info("Trap ingestion enabled on port %d", config.settings.trap_listen_port)

    await asyncio.gather(*loops)


if __name__ == "__main__":
    asyncio.run(main())
