#!/usr/bin/env python3
"""Synthetic ingest load driver (Step 2.5 / plan Step 29).

Bypasses SNMP entirely: generates realistic Parquet batches for N synthetic
devices and pushes them through the real POST /ingest path, isolating the
manager/DuckDB ceiling — the actual 1000-device question.

    python3 scripts/loadtest/ingest_load.py \
        --devices 1000 --interfaces 30 --oids 10 \
        --duration 120 --concurrency 4 \
        --manager-url http://localhost:8001 --api-key "$MANAGER_API_KEY"

Requires: httpx, pyarrow (already dev dependencies of agent/manager).
Emits a JSON report (rows/s, request p50/p99, error/deferral counts) on stdout.
"""

import argparse
import asyncio
import hashlib
import io
import json
import random
import statistics
import time
import uuid
from datetime import datetime, timezone

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

OID_NAMES = [
    "ifInOctets",
    "ifOutOctets",
    "ifInErrors",
    "ifOutErrors",
    "ifOperStatus",
    "ifSpeed",
    "ifHCInOctets",
    "ifHCOutOctets",
    "ifInDiscards",
    "ifOutDiscards",
]


def make_batch(device_start: int, devices_per_batch: int, interfaces: int, oids: int) -> bytes:
    """One Parquet batch: rows for a slice of the synthetic fleet."""
    now = datetime.now(timezone.utc)
    n = devices_per_batch * interfaces * oids
    device_ips, iface_names, oid_names, oid_vals, values = [], [], [], [], []
    for d in range(device_start, device_start + devices_per_batch):
        ip = f"10.{(d >> 8) & 0xFF}.{d & 0xFF}.1"
        for i in range(interfaces):
            for o in range(oids):
                device_ips.append(ip)
                iface_names.append(f"GigabitEthernet0/{i}")
                oid_names.append(OID_NAMES[o % len(OID_NAMES)])
                oid_vals.append(f"1.3.6.1.2.1.2.2.1.{10 + o}.{i}")
                values.append(str(random.randint(0, 10**9)))
    table = pa.table(
        {
            "agent_id": pa.array(["loadtest-agent"] * n),
            "device_ip": pa.array(device_ips),
            "interface_name": pa.array(iface_names),
            "oid_name": pa.array(oid_names),
            "oid": pa.array(oid_vals),
            "value": pa.array(values),
            "collected_at": pa.array([now] * n, type=pa.timestamp("us", tz="UTC")),
        }
    )
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


async def worker(args, results, stop_at, device_slice):
    async with httpx.AsyncClient(timeout=60.0) as client:
        while time.monotonic() < stop_at:
            payload = make_batch(device_slice, args.batch_devices, args.interfaces, args.oids)
            file_id = f"{uuid.uuid4().hex}_polls"
            sha = hashlib.sha256(payload).hexdigest()
            started = time.monotonic()
            try:
                resp = await client.post(
                    f"{args.manager_url}/ingest",
                    files={"file": (f"{file_id}.parquet", payload, "application/octet-stream")},
                    headers={
                        "Authorization": f"Bearer {args.api_key}",
                        "X-File-ID": file_id,
                        "X-SHA256": sha,
                    },
                )
                elapsed = time.monotonic() - started
                if resp.status_code == 200:
                    results["latencies"].append(elapsed)
                    results["rows"] += resp.json().get("rows_ingested", 0)
                elif resp.status_code == 503:
                    results["deferrals"] += 1
                    await asyncio.sleep(1)
                else:
                    results["errors"] += 1
            except httpx.HTTPError:
                results["errors"] += 1
                await asyncio.sleep(1)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devices", type=int, default=1000)
    parser.add_argument("--interfaces", type=int, default=30)
    parser.add_argument("--oids", type=int, default=10)
    parser.add_argument("--batch-devices", type=int, default=25, help="devices per parquet batch (agent-sized)")
    parser.add_argument("--duration", type=int, default=120, help="seconds")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel uploaders (simulated agents)")
    parser.add_argument("--manager-url", default="http://localhost:8001")
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args()

    results = {"latencies": [], "rows": 0, "errors": 0, "deferrals": 0}
    stop_at = time.monotonic() + args.duration
    started = time.monotonic()
    await asyncio.gather(*(worker(args, results, stop_at, w * args.batch_devices) for w in range(args.concurrency)))
    wall = time.monotonic() - started

    lats = sorted(results["latencies"])
    report = {
        "driver": "ingest_load",
        "config": {k: v for k, v in vars(args).items() if k != "api_key"},
        "wall_seconds": round(wall, 1),
        "uploads_ok": len(lats),
        "rows_ingested": results["rows"],
        "rows_per_second": round(results["rows"] / wall, 1) if wall else 0,
        "deferrals_503": results["deferrals"],
        "errors": results["errors"],
        "upload_p50_ms": round(statistics.median(lats) * 1000, 1) if lats else None,
        "upload_p99_ms": round(lats[int(len(lats) * 0.99) - 1] * 1000, 1) if len(lats) >= 2 else None,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
