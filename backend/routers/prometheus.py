"""Prometheus exposition endpoint for per-device/per-interface metrics.

Reads the current device list from Postgres and the latest interface rates from
the manager (which owns DuckDB), and renders standard Prometheus text. Scrapers
authenticate with a dedicated bearer token (PROMETHEUS_SCRAPE_TOKEN), kept
separate from MANAGER_API_KEY so the manager/agent secret never lands in a
scrape config.
"""
import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import Device

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prometheus"])

_RATES_LOOKBACK_HOURS = 0.1


def _require_scrape_token(authorization: str = Header(None)):
    if not settings.prometheus_scrape_token:
        raise HTTPException(status_code=503, detail="Prometheus exporter not configured")
    expected = f"Bearer {settings.prometheus_scrape_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid scrape token")


def _fetch_rates(device_ip: str) -> dict:
    url = f"{settings.manager_url}/internal/metrics/rates"
    resp = httpx.get(url, params={"device_ip": device_ip, "hours": _RATES_LOOKBACK_HOURS},
                     headers={"Authorization": f"Bearer {settings.manager_api_key}"}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


_GAUGES = {
    "snmp_interface_in_bps": "Inbound bits per second",
    "snmp_interface_out_bps": "Outbound bits per second",
    "snmp_interface_utilization_percent": "Interface utilization percent",
    "snmp_interface_errors": "Interface errors over the sample window",
    "snmp_interface_up": "Interface operational status (1=up, 0=down)",
    "snmp_device_up": "Device reachability (1=data received, 0=none)",
}


def _render(devices_rates: list[tuple]) -> str:
    """devices_rates: list of (Device, rates_dict_or_None)."""
    lines: dict[str, list[str]] = {name: [] for name in _GAUGES}

    for device, rates in devices_rates:
        dlabel = f'device="{_esc(device.name)}",ip="{_esc(device.ip_address)}"'
        if rates is None:
            lines["snmp_device_up"].append(f"snmp_device_up{{{dlabel}}} 0")
            continue
        interfaces = rates.get("interfaces", {})
        lines["snmp_device_up"].append(f"snmp_device_up{{{dlabel}}} {1 if interfaces else 0}")
        for name, iface in interfaces.items():
            ilabel = f'{dlabel},interface="{_esc(name)}"'
            lines["snmp_interface_in_bps"].append(
                f"snmp_interface_in_bps{{{ilabel}}} {iface.get('current_in_bps', 0)}")
            lines["snmp_interface_out_bps"].append(
                f"snmp_interface_out_bps{{{ilabel}}} {iface.get('current_out_bps', 0)}")
            if iface.get("utilization_pct") is not None:
                lines["snmp_interface_utilization_percent"].append(
                    f"snmp_interface_utilization_percent{{{ilabel}}} {iface['utilization_pct']}")
            lines["snmp_interface_errors"].append(
                f"snmp_interface_errors{{{ilabel}}} {iface.get('error_count', 0)}")
            status = iface.get("status")
            if status in ("up", "down"):
                lines["snmp_interface_up"].append(
                    f"snmp_interface_up{{{ilabel}}} {1 if status == 'up' else 0}")

    out = []
    for name, help_text in _GAUGES.items():
        if not lines[name]:
            continue
        out.append(f"# HELP {name} {help_text}")
        out.append(f"# TYPE {name} gauge")
        out.extend(lines[name])
    return "\n".join(out) + "\n"


@router.get("/metrics/prometheus", response_class=PlainTextResponse,
            dependencies=[Depends(_require_scrape_token)])
def prometheus_metrics(db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.enabled == True).all()
    devices_rates = []
    for device in devices:
        try:
            devices_rates.append((device, _fetch_rates(device.ip_address)))
        except Exception as exc:
            logger.warning("prometheus: rates fetch failed for %s: %s", device.name, exc)
            devices_rates.append((device, None))
    return _render(devices_rates)
