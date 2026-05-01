from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DeviceConfig(BaseModel):
    id: str
    ip: str
    hostname: Optional[str] = None
    snmp_version: str = "v3"
    username: str
    auth_protocol: str
    auth_password: str
    priv_protocol: str
    priv_password: str


class RegisterRequest(BaseModel):
    hostname: str
    ip: str


class RegisterResponse(BaseModel):
    agent_id: str
    devices: list[DeviceConfig]


class HeartbeatRequest(BaseModel):
    agent_id: str
    pending_uploads: int = 0
    poll_success_rate: float = 1.0


class AddDeviceRequest(BaseModel):
    ip: str
    hostname: Optional[str] = None
    username: str
    auth_protocol: str
    auth_password: str
    priv_protocol: str
    priv_password: str
    assigned_agent_id: Optional[str] = None


class DeviceResponse(BaseModel):
    id: str
    ip: str
    hostname: Optional[str]
    snmp_version: str
    username: str
    auth_protocol: str
    priv_protocol: str
    assigned_agent_id: Optional[str]
    created_at: datetime
    last_polled_at: Optional[datetime]
