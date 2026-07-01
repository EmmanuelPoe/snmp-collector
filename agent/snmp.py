from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UsmUserData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity, nextCmd,
    usmHMACSHAAuthProtocol, usmHMACMD5AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmAesCfb128Protocol, usmAesCfb256Protocol, usmDESPrivProtocol,
)
from models import DeviceConfig

_AUTH = {
    "SHA": usmHMACSHAAuthProtocol,
    "SHA256": usmHMAC256SHA384AuthProtocol,
    "MD5": usmHMACMD5AuthProtocol,
}
_PRIV = {
    "AES": usmAesCfb128Protocol,
    "AES256": usmAesCfb256Protocol,
    "DES": usmDESPrivProtocol,
}

# Default OID set, used as a fallback when the backend supplies no whitelist
# (e.g. older backend or empty collection_configs). When device.oids is present
# it governs collection instead.
_IF_OIDS = {
    "1.3.6.1.2.1.2.2.1.2":   "ifDescr",
    "1.3.6.1.2.1.2.2.1.7":   "ifAdminStatus",
    "1.3.6.1.2.1.2.2.1.8":   "ifOperStatus",
    "1.3.6.1.2.1.2.2.1.10":  "ifInOctets",
    "1.3.6.1.2.1.2.2.1.16":  "ifOutOctets",
    "1.3.6.1.2.1.2.2.1.14":  "ifInErrors",
    "1.3.6.1.2.1.2.2.1.20":  "ifOutErrors",
    "1.3.6.1.2.1.31.1.1.1.6":  "ifHCInOctets",
    "1.3.6.1.2.1.31.1.1.1.10": "ifHCOutOctets",
}

# ifDescr is required to build the interface-name map for every row, so it is
# always walked regardless of the configured whitelist.
_IFDESCR_OID = "1.3.6.1.2.1.2.2.1.2"


def _auth_data(device: DeviceConfig):
    if device.snmp_version == "2c":
        return CommunityData(device.snmp_community or "public")
    return UsmUserData(
        device.username,
        authKey=device.auth_password,
        privKey=device.priv_password,
        authProtocol=_AUTH.get(device.auth_protocol or "SHA", usmHMACSHAAuthProtocol),
        privProtocol=_PRIV.get(device.priv_protocol or "AES", usmAesCfb128Protocol),
    )


def walk_oid(device: DeviceConfig, base_oid: str, max_rows: int = 500) -> list[dict]:
    """Ad-hoc SNMP walk from base_oid, for the MIB browser. Returns [{oid, value}]
    capped at max_rows."""
    auth = _auth_data(device)
    transport = UdpTransportTarget((device.ip, device.snmp_port), timeout=5, retries=1)
    engine = SnmpEngine()
    rows = []
    for err_ind, err_stat, _, var_binds in nextCmd(
        engine, auth, transport, ContextData(),
        ObjectType(ObjectIdentity(base_oid)),
        lexicographicMode=False,
    ):
        if err_ind:
            raise RuntimeError(str(err_ind))
        if err_stat:
            raise RuntimeError(err_stat.prettyPrint())
        for oid, val in var_binds:
            rows.append({"oid": str(oid), "value": str(val)})
            if len(rows) >= max_rows:
                return rows
    return rows


# LLDP-MIB (1.0.8802.1.1.2) remote-systems table columns, for topology discovery.
_LLDP_REM_COLUMNS = {
    "remote_chassis_id": "1.0.8802.1.1.2.1.4.1.1.5",
    "remote_port_id":    "1.0.8802.1.1.2.1.4.1.1.7",
    "remote_port_desc":  "1.0.8802.1.1.2.1.4.1.1.8",
    "remote_sysname":    "1.0.8802.1.1.2.1.4.1.1.9",
}
# lldpLocPortDesc, indexed by local port number — maps a neighbour to our port.
_LLDP_LOC_PORTDESC = "1.0.8802.1.1.2.1.3.7.1.4"


def walk_lldp(device: DeviceConfig, max_rows: int = 1000) -> list[dict]:
    """Walk the LLDP remote-systems table for topology discovery. Returns one dict
    per discovered neighbour. Empty list if the device exposes no LLDP data."""
    auth = _auth_data(device)
    transport = UdpTransportTarget((device.ip, device.snmp_port), timeout=5, retries=1)
    engine = SnmpEngine()

    # Neighbours keyed by the shared table index (timeMark.localPortNum.remIndex).
    neighbours: dict[str, dict] = {}
    for field, base_oid in _LLDP_REM_COLUMNS.items():
        for err_ind, err_stat, _, var_binds in nextCmd(
            engine, auth, transport, ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if err_ind or err_stat:
                break
            for oid, val in var_binds:
                index = str(oid)[len(base_oid) + 1:]
                parts = index.split(".")
                if len(parts) < 2:
                    continue
                row = neighbours.setdefault(index, {"local_port_num": parts[1]})
                row[field] = str(val)
        if len(neighbours) >= max_rows:
            break

    # Map local port numbers to human-readable local port descriptions.
    local_ports: dict[str, str] = {}
    for err_ind, err_stat, _, var_binds in nextCmd(
        engine, auth, transport, ContextData(),
        ObjectType(ObjectIdentity(_LLDP_LOC_PORTDESC)),
        lexicographicMode=False,
    ):
        if err_ind or err_stat:
            break
        for oid, val in var_binds:
            port_num = str(oid).rsplit(".", 1)[-1]
            local_ports[port_num] = str(val)

    result = []
    for row in neighbours.values():
        row["local_port_desc"] = local_ports.get(row["local_port_num"])
        result.append(row)
    return result


def walk_device(device: DeviceConfig) -> list[dict]:
    auth = _auth_data(device)
    transport = UdpTransportTarget((device.ip, device.snmp_port), timeout=5, retries=2)
    engine = SnmpEngine()

    interface_names: dict[str, str] = {}
    for err_ind, err_stat, _, var_binds in nextCmd(
        engine, auth, transport, ContextData(),
        ObjectType(ObjectIdentity(_IFDESCR_OID)),
        lexicographicMode=False,
    ):
        if err_ind or err_stat:
            break
        for oid, val in var_binds:
            idx = str(oid).rsplit(".", 1)[-1]
            interface_names[idx] = str(val)

    # Whitelist from the backend governs collection; fall back to the default set.
    oid_map = {o["oid"]: o["oid_name"] for o in device.oids} if device.oids else dict(_IF_OIDS)

    rows = []
    for base_oid, oid_name in oid_map.items():
        if base_oid == _IFDESCR_OID:
            continue
        for err_ind, err_stat, _, var_binds in nextCmd(
            engine, auth, transport, ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if err_ind or err_stat:
                break
            for oid, val in var_binds:
                idx = str(oid).rsplit(".", 1)[-1]
                rows.append({
                    "interface_name": interface_names.get(idx),
                    "oid_name": oid_name,
                    "oid": str(oid),
                    "value": str(val),
                })
    return rows
