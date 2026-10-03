#!/usr/bin/env python3
"""Register (or remove) the synthetic ingest fleet as real Postgres devices.

ingest_load.py writes metrics for the addresses fleet.synthetic_ip(d) yields, but the
backend resolves device_id -> ip from Postgres, so without matching Device rows
every query-side benchmark runs at devices_seen=1. This registers them.

    python3 scripts/loadtest/register_fleet.py --password "$ADMIN_PASSWORD" --devices 2000
    python3 scripts/loadtest/register_fleet.py --password "$ADMIN_PASSWORD" --cleanup

Devices are assigned to a non-existent agent so no real agent tries to poll the
fake addresses. Names are loadtest-NNNN; re-running is idempotent.
"""

import argparse
import asyncio

import httpx
from fleet import synthetic_ip

PREFIX = "loadtest-"
NOBODY = "loadtest-nobody"


async def login(client: httpx.AsyncClient, args) -> None:
    resp = await client.post(f"{args.api_url}/auth/login", data={"username": args.email, "password": args.password})
    resp.raise_for_status()
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"


async def existing_loadtest_devices(client, args) -> dict[str, int]:
    found, skip = {}, 0
    while True:
        resp = await client.get(f"{args.api_url}/devices", params={"skip": skip, "limit": 1000})
        resp.raise_for_status()
        page = resp.json()
        found.update({d["name"]: d["id"] for d in page if d["name"].startswith(PREFIX)})
        if len(page) < 1000:
            return found
        skip += 1000


async def bounded(sem, coro):
    async with sem:
        return await coro


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost/api")
    parser.add_argument("--email", default="admin@localhost")
    parser.add_argument("--password", required=True)
    parser.add_argument("--devices", type=int, default=2000)
    parser.add_argument("--enabled", action="store_true", help="enable devices so the alert evaluator walks them")
    parser.add_argument("--cleanup", action="store_true", help="delete every loadtest-* device and exit")
    parser.add_argument("--concurrency", type=int, default=16)
    args = parser.parse_args()

    sem = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(timeout=30.0) as client:
        await login(client, args)
        have = await existing_loadtest_devices(client, args)

        if args.cleanup:
            results = await asyncio.gather(
                *(bounded(sem, client.delete(f"{args.api_url}/devices/{i}")) for i in have.values())
            )
            print(f"deleted {sum(r.status_code == 204 for r in results)} of {len(have)} loadtest devices")
            return

        async def create(d: int):
            return await client.post(
                f"{args.api_url}/devices",
                json={
                    "name": f"{PREFIX}{d:04d}",
                    "ip_address": synthetic_ip(d),
                    "enabled": args.enabled,
                    "assigned_agent_id": NOBODY,
                    "device_type": "switch",
                    "tags": ["loadtest"],
                },
            )

        todo = [d for d in range(args.devices) if f"{PREFIX}{d:04d}" not in have]
        results = await asyncio.gather(*(bounded(sem, create(d)) for d in todo))
        failed = [r for r in results if r.status_code != 201]
        print(f"registered {len(todo) - len(failed)} new, {len(have)} already present, {len(failed)} failed")
        if failed:
            print(failed[0].status_code, failed[0].text[:200])
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
