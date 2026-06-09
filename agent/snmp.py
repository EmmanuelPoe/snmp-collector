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
