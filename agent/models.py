from pydantic import BaseModel
from typing import Optional


class DeviceConfig(BaseModel):
    id: str
    ip: str
    hostname: Optional[str] = None
    snmp_version: str = "2c"
    snmp_community: Optional[str] = None
    snmp_port: int = 161
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None
    priv_password: Optional[str] = None
    oids: Optional[list[dict]] = None


class PollRow(BaseModel):
    agent_id: str
    device_ip: str
    interface_name: Optional[str]
    oid_name: str
    oid: str
    value: str
    collected_at: str
