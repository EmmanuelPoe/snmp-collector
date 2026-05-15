from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class DeviceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    ip_address: str
    snmp_version: str = Field(default="2c", pattern="^(2c|3)$")
    snmp_community: str = Field(default="public", min_length=1)
    snmp_port: int = Field(default=161, ge=1, le=65535)
    snmp_modules: List[str] = Field(default=["if_mib"])
    device_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    enabled: bool = True
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None
    priv_password: Optional[str] = None
    assigned_agent_id: Optional[str] = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    ip_address: Optional[str] = None
    snmp_version: Optional[str] = Field(None, pattern="^(2c|3)$")
    snmp_community: Optional[str] = Field(None, min_length=1)
    snmp_port: Optional[int] = Field(None, ge=1, le=65535)
    snmp_modules: Optional[List[str]] = None
    device_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None
    priv_password: Optional[str] = None
    assigned_agent_id: Optional[str] = None


class DeviceResponse(BaseModel):
    id: int
    name: str
    ip_address: str
    snmp_version: str
    snmp_community: str
    snmp_port: int
    snmp_modules: Optional[List[str]] = None
    device_type: Optional[str] = None
    description: Optional[str] = None
    enabled: bool
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    # auth_password and priv_password intentionally excluded from response
    priv_protocol: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MetricResponse(BaseModel):
    id: int
    device_id: int
    timestamp: datetime
    interface_name: Optional[str] = None
    interface_index: Optional[int] = None
    oid: str
    oid_name: Optional[str] = None
    value: Optional[float] = None
    value_type: Optional[str] = None

    class Config:
        from_attributes = True


class CollectionConfigBase(BaseModel):
    oid: str = Field(..., min_length=1)
    oid_name: str = Field(..., min_length=1)
    description: Optional[str] = None
    enabled: bool = True


class CollectionConfigCreate(CollectionConfigBase):
    pass


class CollectionConfigUpdate(BaseModel):
    oid_name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class CollectionConfigResponse(CollectionConfigBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
