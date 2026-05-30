from typing import Optional
from datetime import datetime, timedelta, timezone
from datetime import datetime as _dt

from fastapi import APIRouter, Depends, Query

from auth import require_api_key
from db import query

router = APIRouter(prefix="/internal/metrics", tags=["metrics"])


@router.get("")
async def query_metrics(
    device_ip: str,
    interface_name: Optional[str] = None,
    oid_name: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(default=1000, le=10000),
    _: str = Depends(require_api_key),
):
    conditions = ["device_ip = ?"]
    params: list = [device_ip]
    if interface_name:
        conditions.append("interface_name = ?")
        params.append(interface_name)
    if oid_name:
        conditions.append("oid_name = ?")
        params.append(oid_name)
    if start_time:
        conditions.append("collected_at >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("collected_at <= ?")
        params.append(end_time)
    params.append(limit)

    rows = await query(
        "SELECT agent_id, device_ip, interface_name, oid_name, oid, value, collected_at "
        f"FROM snmp_polls WHERE {' AND '.join(conditions)} "
        "ORDER BY collected_at DESC LIMIT ?",
        params,
    )
    return [
        {
            "agent_id": r[0], "device_ip": r[1], "interface_name": r[2],
            "oid_name": r[3], "oid": r[4], "value": r[5], "collected_at": r[6],
        }
        for r in rows
    ]


@router.get("/available")
async def available_metrics(
    device_ip: str,
    _: str = Depends(require_api_key),
):
    ifaces = await query(
        "SELECT DISTINCT interface_name FROM snmp_polls "
        "WHERE device_ip = ? AND interface_name IS NOT NULL",
        [device_ip],
    )
    oids = await query(
        "SELECT DISTINCT oid_name FROM snmp_polls "
        "WHERE device_ip = ? AND oid_name IS NOT NULL",
        [device_ip],
    )
    return {
        "modules": {
            "if_mib": {
                "interfaces": sorted(r[0] for r in ifaces),
                "metrics": sorted(r[0] for r in oids),
            }
        }
    }


@router.get("/rates")
async def interface_rates(
    device_ip: str,
    hours: float = Query(default=1.0, gt=0, le=168),
    _: str = Depends(require_api_key),
):
    cutoff = _dt.now(timezone.utc) - timedelta(hours=hours)
    rows = await query(
        "SELECT interface_name, oid_name, TRY_CAST(value AS DOUBLE), collected_at "
        "FROM snmp_polls "
        "WHERE device_ip = ? AND collected_at >= ? AND interface_name IS NOT NULL "
        "ORDER BY interface_name, oid_name, collected_at ASC",
        [device_ip, cutoff],
    )

    oid_series: dict[str, dict[str, list]] = {}
    for iface, oid_name, value, ts in rows:
        oid_series.setdefault(iface, {}).setdefault(oid_name, []).append((value, ts))

    def _deltas(pts: list) -> list:
        result = []
        for i in range(1, len(pts)):
            v1, t1 = pts[i - 1]
            v2, t2 = pts[i]
            if v1 is None or v2 is None:
                continue
            dt_sec = (t2 - t1).total_seconds()
            if dt_sec <= 0:
                continue
            result.append((max(0.0, v2 - v1) / dt_sec, t2))
        return result

    interfaces: dict = {}
    for iface, oids in oid_series.items():
        in_pts = oids.get("ifHCInOctets") or oids.get("ifInOctets", [])
        out_pts = oids.get("ifHCOutOctets") or oids.get("ifOutOctets", [])
        in_d = _deltas(in_pts)
        out_d = _deltas(out_pts)

        current_in_bps = in_d[-1][0] * 8 if in_d else 0.0
        current_out_bps = out_d[-1][0] * 8 if out_d else 0.0

        n = max(len(in_d), len(out_d))
        sparkline = []
        for i in range(n):
            in_val = in_d[i][0] * 8 if i < len(in_d) else 0.0
            out_val = out_d[i][0] * 8 if i < len(out_d) else 0.0
            ts = (in_d[i][1] if i < len(in_d) else out_d[i][1])
            sparkline.append({"timestamp": ts.isoformat(), "in_bps": in_val, "out_bps": out_val})

        status = None
        if "ifOperStatus" in oids and oids["ifOperStatus"]:
            sv = oids["ifOperStatus"][-1][0]
            if sv is not None:
                status = {1.0: "up", 2.0: "down"}.get(sv, "unknown")

        speed_bps = None
        if "ifHighSpeed" in oids and oids["ifHighSpeed"]:
            v = oids["ifHighSpeed"][-1][0]
            if v is not None and v > 0:
                speed_bps = v * 1_000_000
        elif "ifSpeed" in oids and oids["ifSpeed"]:
            v = oids["ifSpeed"][-1][0]
            if v is not None and v > 0:
                speed_bps = v

        util = None
        if speed_bps:
            util = round(max(current_in_bps, current_out_bps) / speed_bps * 100, 4)

        error_count = 0
        for err_oid in ("ifInErrors", "ifOutErrors"):
            if err_oid in oids:
                for d_val, _ in _deltas(oids[err_oid]):
                    error_count += int(d_val)

        interfaces[iface] = {
            "status": status,
            "speed_bps": speed_bps,
            "current_in_bps": current_in_bps,
            "current_out_bps": current_out_bps,
            "utilization_pct": util,
            "error_count": error_count,
            "sparkline": sparkline,
        }

    return {"interfaces": interfaces}


@router.get("/history")
async def interface_history(
    device_ip: str,
    interface_name: str,
    hours: float = Query(default=1.0, gt=0, le=168),
    buckets: int = Query(default=60, ge=10, le=200),
    _: str = Depends(require_api_key),
):
    cutoff = _dt.now(timezone.utc) - timedelta(hours=hours)
    rows = await query(
        "SELECT oid_name, TRY_CAST(value AS DOUBLE), collected_at "
        "FROM snmp_polls "
        "WHERE device_ip = ? AND interface_name = ? AND collected_at >= ? "
        "  AND oid_name IN ('ifInOctets','ifOutOctets','ifHCInOctets','ifHCOutOctets','ifInErrors','ifOutErrors') "
        "ORDER BY oid_name, collected_at ASC",
        [device_ip, interface_name, cutoff],
    )

    oid_series: dict[str, list] = {}
    for oid_name, value, ts in rows:
        oid_series.setdefault(oid_name, []).append((value, ts))

    def _rates(pts: list) -> list[tuple]:
        result = []
        for i in range(1, len(pts)):
            v1, t1 = pts[i - 1]
            v2, t2 = pts[i]
            if v1 is None or v2 is None:
                continue
            dt_sec = (t2 - t1).total_seconds()
            if dt_sec <= 0:
                continue
            delta = max(0.0, v2 - v1)
            result.append((delta / dt_sec * 8, t2))  # bytes/s → bps
        return result

    in_pts = oid_series.get("ifHCInOctets") or oid_series.get("ifInOctets", [])
    out_pts = oid_series.get("ifHCOutOctets") or oid_series.get("ifOutOctets", [])
    in_rates = _rates(in_pts)
    out_rates = _rates(out_pts)
    in_err_rates = _rates(oid_series.get("ifInErrors", []))
    out_err_rates = _rates(oid_series.get("ifOutErrors", []))

    bucket_sec = (hours * 3600) / buckets
    now = _dt.now(timezone.utc)

    def _bucket(rate_pts: list, start: _dt, bsec: float, n: int) -> list:
        result = []
        for i in range(n):
            b_start = start + timedelta(seconds=i * bsec)
            b_end = b_start + timedelta(seconds=bsec)
            vals = [v for v, t in rate_pts if b_start <= t < b_end]
            result.append(sum(vals) / len(vals) if vals else None)
        return result

    in_b = _bucket(in_rates, cutoff, bucket_sec, buckets)
    out_b = _bucket(out_rates, cutoff, bucket_sec, buckets)
    in_err_b = _bucket(in_err_rates, cutoff, bucket_sec, buckets)
    out_err_b = _bucket(out_err_rates, cutoff, bucket_sec, buckets)

    series = [
        {
            "timestamp": (cutoff + timedelta(seconds=(i + 1) * bucket_sec)).isoformat(),
            "in_bps": in_b[i],
            "out_bps": out_b[i],
            "in_errors": in_err_b[i],
            "out_errors": out_err_b[i],
        }
        for i in range(buckets)
    ]
    return {"series": series}
