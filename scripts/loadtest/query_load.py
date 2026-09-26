#!/usr/bin/env python3
"""Query-side load driver (Step 2.5 / plan Step 29): a dashboard-open fleet.

Concurrent calls against the backend's device/metrics/rates endpoints plus one
Prometheus-exporter scrape, measuring read latency while ingest is under load.

    python3 scripts/loadtest/query_load.py \
        --api-url http://localhost/api --email admin@localhost \
        --password "$ADMIN_PASSWORD" --duration 60 --concurrency 8
"""

import argparse
import asyncio
import json
import random
import statistics
import time

import httpx


async def dashboard_worker(client, args, device_ids, results, stop_at):
    while time.monotonic() < stop_at:
        calls = [("GET", f"{args.api_url}/alerts/count", None)]
        if device_ids:
            did = random.choice(device_ids)
            calls += [
                ("GET", f"{args.api_url}/metrics/rates/{did}?hours=1", None),
                ("GET", f"{args.api_url}/metrics/latest/{did}?limit=50", None),
            ]
        for method, url, _ in calls:
            started = time.monotonic()
            try:
                resp = await client.request(method, url)
                if resp.status_code == 200:
                    results["latencies"].append(time.monotonic() - started)
                else:
                    results["errors"] += 1
            except httpx.HTTPError:
                results["errors"] += 1
        await asyncio.sleep(0.2)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost/api")
    parser.add_argument("--email", default="admin@localhost")
    parser.add_argument("--password", required=True)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--scrape-token", default="", help="PROMETHEUS_SCRAPE_TOKEN, if set")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{args.api_url}/auth/login",
            data={"username": args.email, "password": args.password},
        )
        resp.raise_for_status()
        client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"

        devices = (await client.get(f"{args.api_url}/devices")).json()
        device_ids = [d["id"] for d in devices]

        results = {"latencies": [], "errors": 0}
        stop_at = time.monotonic() + args.duration
        tasks = [dashboard_worker(client, args, device_ids, results, stop_at) for _ in range(args.concurrency)]
        started = time.monotonic()
        await asyncio.gather(*tasks)
        wall = time.monotonic() - started

        scrape_ms = None
        if args.scrape_token:
            t0 = time.monotonic()
            sr = await client.get(
                f"{args.api_url}/metrics/prometheus",
                headers={"Authorization": f"Bearer {args.scrape_token}"},
            )
            if sr.status_code == 200:
                scrape_ms = round((time.monotonic() - t0) * 1000, 1)

    lats = sorted(results["latencies"])
    report = {
        "driver": "query_load",
        "devices_seen": len(device_ids),
        "wall_seconds": round(wall, 1),
        "requests_ok": len(lats),
        "requests_per_second": round(len(lats) / wall, 1) if wall else 0,
        "errors": results["errors"],
        "query_p50_ms": round(statistics.median(lats) * 1000, 1) if lats else None,
        "query_p99_ms": round(lats[int(len(lats) * 0.99) - 1] * 1000, 1) if len(lats) >= 2 else None,
        "exporter_scrape_ms": scrape_ms,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
