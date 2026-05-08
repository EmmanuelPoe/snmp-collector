import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

import config
from models import DeviceConfig
from snmp import walk_device
from uploader import UploadBuffer


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "time": self.formatTime(record),
            "level": record.levelname,
            "service": "agent",
            "logger": record.name,
            "message": record.getMessage(),
        })

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
log = logging.getLogger(__name__)

_agent_id: str | None = None
_buffer: UploadBuffer | None = None


async def _register() -> str:
    id_file = Path(config.settings.agent_id_path)
    if id_file.exists():
        stored = id_file.read_text().strip()
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{config.settings.manager_url}/config/{stored}",
                    headers={"Authorization": f"Bearer {config.settings.manager_api_key}"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    log.info("Reusing agent_id: %s", stored)
                    return stored
            except httpx.RequestError:
                pass

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
                agent_id = resp.json()["agent_id"]
                id_file.parent.mkdir(parents=True, exist_ok=True)
                id_file.write_text(agent_id)
                log.info("Registered as agent_id: %s", agent_id)
                return agent_id
        except Exception as exc:
            log.warning("Registration failed: %s — retrying in 10s", exc)
            await asyncio.sleep(10)


async def _heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(30)
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{config.settings.manager_url}/heartbeat",
                    json={"agent_id": _agent_id, "pending_uploads": _buffer.pending_count() if _buffer else 0},
                    headers={"Authorization": f"Bearer {config.settings.manager_api_key}"},
                    timeout=5.0,
                )
        except Exception as exc:
            log.debug("Heartbeat failed: %s", exc)


async def _fetch_devices() -> list[DeviceConfig]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{config.settings.manager_url}/config/{_agent_id}",
            headers={"Authorization": f"Bearer {config.settings.manager_api_key}"},
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


async def main() -> None:
    global _agent_id, _buffer
    _agent_id = await _register()
    _buffer = UploadBuffer(agent_id=_agent_id)

    await asyncio.gather(
        _heartbeat_loop(),
        _poll_loop(),
        _retry_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
