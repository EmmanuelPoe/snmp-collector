import asyncio
from datetime import datetime, datetime as _dt, timedelta, timezone
from typing import Optional

from auth import require_api_key
from db import query
from fastapi import APIRouter, Depends, Query

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
            "agent_id": r[0],
            "device_ip": r[1],
            "interface_name": r[2],
            "oid_name": r[3],
            "oid": r[4],
            "value": r[5],
            "collected_at": r[6],
        }
        for r in rows
    ]


@router.get("/available")
async def available_metrics(
    device_ip: str,
    _: str = Depends(require_api_key),
):
    ifaces = await query(
        "SELECT DISTINCT interface_name FROM snmp_polls WHERE device_ip = ? AND interface_name IS NOT NULL",
        [device_ip],
    )
    oids = await query(
        "SELECT DISTINCT oid_name FROM snmp_polls WHERE device_ip = ? AND oid_name IS NOT NULL",
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
            ts = in_d[i][1] if i < len(in_d) else out_d[i][1]
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


_FLEET_CACHE_TTL_S = 15.0
_FLEET_CACHE_MAX = 32
_fleet_cache: dict[tuple, tuple[float, dict]] = {}
_fleet_locks: dict[tuple, asyncio.Lock] = {}
# The leaderboard only needs "current" rates (last 10 min) plus one earlier sample
# per counter, so don't window-scan the whole `hours` span a second time.
_TOP_RAW_WINDOW = timedelta(minutes=15)

# Octet counters only; HC variants win when an interface reports both so a
# 64-bit and a 32-bit counter for the same port are never summed twice. A counter
# reset or 32-bit wrap (v < pv) drops the sample rather than reporting 0 bps.
_FLEET_RATES_CTE = """
WITH raw AS (
  SELECT device_ip, interface_name,
         CASE WHEN oid_name LIKE '%In%' THEN 'in' ELSE 'out' END AS dir,
         oid_name LIKE 'ifHC%' AS is_hc,
         TRY_CAST(value AS DOUBLE) AS v, collected_at
  FROM snmp_polls
  WHERE collected_at >= ? AND interface_name IS NOT NULL
    AND oid_name IN ('ifHCInOctets','ifInOctets','ifHCOutOctets','ifOutOctets')
),
pref AS (
  SELECT *, MAX(is_hc::INT) OVER (PARTITION BY device_ip, interface_name, dir) AS any_hc
  FROM raw
),
lagged AS (
  SELECT device_ip, interface_name, dir, collected_at, v,
         LAG(v) OVER w AS pv, LAG(collected_at) OVER w AS pt
  FROM pref
  WHERE is_hc::INT = any_hc
  WINDOW w AS (PARTITION BY device_ip, interface_name, dir ORDER BY collected_at)
),
rates AS (
  SELECT device_ip, interface_name, dir, collected_at,
         (v - pv) / date_diff('millisecond', pt, collected_at) * 8000.0 AS bps
  FROM lagged
  WHERE pv IS NOT NULL AND v >= pv AND date_diff('millisecond', pt, collected_at) > 0
)
"""


async def _fleet_traffic(hours: float, top: int) -> dict:
    now = _dt.now(timezone.utc)
    bucket_s = max(60, int(hours * 3600 / 60))

    series_rows = await query(
        _FLEET_RATES_CTE
        + """
, per_iface AS (
  SELECT to_timestamp(floor(epoch(collected_at) / ?) * ?) AS bucket,
         device_ip, interface_name, dir, AVG(bps) AS bps
  FROM rates GROUP BY ALL
)
SELECT bucket,
       SUM(bps) FILTER (WHERE dir = 'in'),
       SUM(bps) FILTER (WHERE dir = 'out'),
       COUNT(DISTINCT device_ip)
FROM per_iface GROUP BY bucket ORDER BY bucket
""",
        [now - timedelta(hours=hours), bucket_s, bucket_s],
    )

    # "Current" = the last rate inside a short window, so a device that stopped
    # reporting drops out of the leaderboard instead of pinning old numbers.
    top_rows = await query(
        _FLEET_RATES_CTE
        + """
, latest AS (
  SELECT device_ip, interface_name, dir, arg_max(bps, collected_at) AS bps
  FROM rates WHERE collected_at >= ? GROUP BY ALL
),
cur AS (
  SELECT device_ip, interface_name,
         COALESCE(MAX(bps) FILTER (WHERE dir = 'in'), 0) AS in_bps,
         COALESCE(MAX(bps) FILTER (WHERE dir = 'out'), 0) AS out_bps
  FROM latest GROUP BY ALL
),
speed AS (
  SELECT device_ip, interface_name,
         COALESCE(
           arg_max(TRY_CAST(value AS DOUBLE), collected_at) FILTER (WHERE oid_name = 'ifHighSpeed') * 1000000,
           arg_max(TRY_CAST(value AS DOUBLE), collected_at) FILTER (WHERE oid_name = 'ifSpeed')
         ) AS speed_bps
  FROM snmp_polls
  WHERE collected_at >= ? AND oid_name IN ('ifHighSpeed','ifSpeed') AND interface_name IS NOT NULL
  GROUP BY ALL
)
SELECT c.device_ip, c.interface_name, c.in_bps, c.out_bps,
       CASE WHEN s.speed_bps > 0 THEN GREATEST(c.in_bps, c.out_bps) / s.speed_bps * 100 END AS util
FROM cur c LEFT JOIN speed s USING (device_ip, interface_name)
""",
        [now - _TOP_RAW_WINDOW, now - timedelta(minutes=10), now - timedelta(minutes=10)],
    )

    def _iface(r) -> dict:
        return {
            "device_ip": r[0],
            "interface_name": r[1],
            "in_bps": r[2],
            "out_bps": r[3],
            "utilization_pct": round(r[4], 2) if r[4] is not None else None,
        }

    ifaces = [_iface(r) for r in top_rows]
    by_traffic = sorted(ifaces, key=lambda i: max(i["in_bps"], i["out_bps"]), reverse=True)[:top]
    by_util = sorted(
        (i for i in ifaces if i["utilization_pct"] is not None),
        key=lambda i: i["utilization_pct"],
        reverse=True,
    )[:top]
    return {
        "series": [
            {"timestamp": r[0].isoformat(), "in_bps": r[1] or 0.0, "out_bps": r[2] or 0.0, "devices": r[3]}
            for r in series_rows
        ],
        "totals": {
            "in_bps": sum(i["in_bps"] for i in ifaces),
            "out_bps": sum(i["out_bps"] for i in ifaces),
            "interfaces": len(ifaces),
            "devices": len({i["device_ip"] for i in ifaces}),
        },
        "top_by_traffic": by_traffic,
        "top_by_utilization": by_util,
    }


@router.get("/fleet-traffic")
async def fleet_traffic(
    hours: float = Query(default=1.0, gt=0, le=24),
    top: int = Query(default=10, ge=1, le=50),
    _: str = Depends(require_api_key),
):
    """Fleet-wide throughput series plus top-N interfaces, in one aggregate
    query — replaces the dashboard's per-device /rates fan-out. Cached briefly
    because every open dashboard asks for the same answer and queries share the
    DuckDB lock with ingest."""
    import time

    # Quantise so varied float `hours` can't mint unbounded cache keys.
    hours = max(0.25, round(hours * 4) / 4)
    key = (hours, top)

    def _fresh():
        hit = _fleet_cache.get(key)
        return hit[1] if hit and time.monotonic() - hit[0] < _FLEET_CACHE_TTL_S else None

    if (cached := _fresh()) is not None:
        return cached
    # Single flight: concurrent misses wait for one computation instead of each
    # running the aggregate while holding the DuckDB lock ingest also needs.
    async with _fleet_locks.setdefault(key, asyncio.Lock()):
        if (cached := _fresh()) is not None:
            return cached
        result = await _fleet_traffic(hours, top)
        now = time.monotonic()
        for k in [k for k, (ts, _) in _fleet_cache.items() if now - ts >= _FLEET_CACHE_TTL_S]:
            del _fleet_cache[k]
        if len(_fleet_cache) >= _FLEET_CACHE_MAX:
            _fleet_cache.pop(next(iter(_fleet_cache)))
        _fleet_cache[key] = (now, result)
        return result


@router.get("/summary")
async def interface_summary(
    device_ip: str,
    hours: float = Query(default=24.0, gt=0, le=8760),
    _: str = Depends(require_api_key),
):
    """Per-interface max/avg in/out bps and utilization over the window — the
    aggregate behind CSV report export."""
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
            result.append(max(0.0, v2 - v1) / dt_sec)
        return result

    def _max(xs):
        return round(max(xs), 2) if xs else 0.0

    def _avg(xs):
        return round(sum(xs) / len(xs), 2) if xs else 0.0

    interfaces: dict = {}
    for iface, oids in oid_series.items():
        in_bps = [d * 8 for d in _deltas(oids.get("ifHCInOctets") or oids.get("ifInOctets", []))]
        out_bps = [d * 8 for d in _deltas(oids.get("ifHCOutOctets") or oids.get("ifOutOctets", []))]

        speed_bps = None
        if oids.get("ifHighSpeed") and oids["ifHighSpeed"][-1][0]:
            speed_bps = oids["ifHighSpeed"][-1][0] * 1_000_000
        elif oids.get("ifSpeed") and oids["ifSpeed"][-1][0]:
            speed_bps = oids["ifSpeed"][-1][0]

        util_series = []
        if speed_bps:
            n = max(len(in_bps), len(out_bps))
            for i in range(n):
                iv = in_bps[i] if i < len(in_bps) else 0.0
                ov = out_bps[i] if i < len(out_bps) else 0.0
                util_series.append(max(iv, ov) / speed_bps * 100)

        interfaces[iface] = {
            "max_in_bps": _max(in_bps),
            "avg_in_bps": _avg(in_bps),
            "max_out_bps": _max(out_bps),
            "avg_out_bps": _avg(out_bps),
            "speed_bps": speed_bps,
            "max_utilization_pct": round(max(util_series), 2) if util_series else None,
            "avg_utilization_pct": round(sum(util_series) / len(util_series), 2) if util_series else None,
            "samples": max(len(in_bps), len(out_bps)),
        }

    return {"interfaces": interfaces}


@router.get("/baseline")
async def interface_baseline(
    device_ip: str,
    days: float = Query(default=7.0, gt=0, le=90),
    _: str = Depends(require_api_key),
):
    """Per-interface p95 of in/out bps over the window — the rolling baseline
    used for anomaly detection. Counter resets (negative deltas) are excluded."""
    cutoff = _dt.now(timezone.utc) - timedelta(days=days)
    rows = await query(
        """
        WITH d AS (
          SELECT interface_name, oid_name,
            TRY_CAST(value AS DOUBLE) - LAG(TRY_CAST(value AS DOUBLE))
              OVER (PARTITION BY interface_name, oid_name ORDER BY collected_at) AS dv,
            date_diff('second',
              LAG(collected_at) OVER (PARTITION BY interface_name, oid_name ORDER BY collected_at),
              collected_at) AS dt
          FROM snmp_polls
          WHERE device_ip = ? AND collected_at >= ? AND interface_name IS NOT NULL
            AND oid_name IN ('ifHCInOctets','ifInOctets','ifHCOutOctets','ifOutOctets')
        )
        SELECT interface_name, oid_name, quantile_cont((dv / dt) * 8, 0.95), COUNT(*)
        FROM d
        WHERE dv >= 0 AND dt > 0
        GROUP BY interface_name, oid_name
        """,
        [device_ip, cutoff],
    )

    raw: dict[str, dict[str, tuple]] = {}
    for iface, oid_name, p95, cnt in rows:
        raw.setdefault(iface, {})[oid_name] = (p95, cnt)

    interfaces = {}
    for iface, oids in raw.items():
        inp = oids.get("ifHCInOctets") or oids.get("ifInOctets")
        outp = oids.get("ifHCOutOctets") or oids.get("ifOutOctets")
        interfaces[iface] = {
            "in_p95_bps": round(inp[0], 2) if inp and inp[0] is not None else None,
            "in_samples": inp[1] if inp else 0,
            "out_p95_bps": round(outp[0], 2) if outp and outp[0] is not None else None,
            "out_samples": outp[1] if outp else 0,
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


@router.get("/traps")
async def query_traps(
    device_ip: Optional[str] = None,
    trap_oid: Optional[str] = None,
    hours: float = Query(default=24.0, gt=0, le=720),
    limit: int = Query(default=200, le=1000),
    _: str = Depends(require_api_key),
):
    cutoff = _dt.now(timezone.utc) - timedelta(hours=hours)
    conditions = ["received_at >= ?"]
    params: list = [cutoff]
    if device_ip:
        conditions.append("device_ip = ?")
        params.append(device_ip)
    if trap_oid:
        conditions.append("trap_oid LIKE ?")
        params.append(f"%{trap_oid}%")
    params.append(limit)

    rows = await query(
        f"SELECT agent_id, device_ip, trap_oid, varbinds, received_at "
        f"FROM snmp_traps WHERE {' AND '.join(conditions)} "
        f"ORDER BY received_at DESC LIMIT ?",
        params,
    )
    return [
        {
            "agent_id": r[0],
            "device_ip": r[1],
            "trap_oid": r[2],
            "varbinds": r[3],
            "received_at": r[4],
        }
        for r in rows
    ]
