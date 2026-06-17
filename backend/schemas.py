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
    tags: List[str] = []


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
    tags: Optional[List[str]] = None


class DeviceResponse(BaseModel):
    id: int
    name: str
    ip_address: str
    snmp_version: str
    snmp_port: int
    snmp_modules: Optional[List[str]] = None
    device_type: Optional[str] = None
    description: Optional[str] = None
    enabled: bool
    assigned_agent_id: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeviceCredentialsResponse(BaseModel):
    snmp_community: Optional[str] = None
    username: Optional[str] = None
    auth_protocol: Optional[str] = None
    priv_protocol: Optional[str] = None

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
    oid_name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    enabled: Optional[bool] = None


class CollectionConfigResponse(CollectionConfigBase):
    id: int
    required: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    device_id: Optional[int] = None
    agent_id: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    status: str

    class Config:
        from_attributes = True


class AlertCountResponse(BaseModel):
    open: int


class AlertRuleCreate(BaseModel):
    bandwidth_in_pct: Optional[float] = Field(None, ge=0, le=100)
    bandwidth_out_pct: Optional[float] = Field(None, ge=0, le=100)
    error_rate: Optional[float] = Field(None, ge=0)
    enabled: bool = True


class AlertRuleResponse(AlertRuleCreate):
    id: int
    device_id: int

    class Config:
        from_attributes = True


class NotificationChannelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(slack|webhook)$")
    url: str = Field(..., min_length=1, max_length=1024)
    severity_filter: List[str] = Field(default=["critical", "warning", "info"])
    enabled: bool = True


class NotificationChannelCreate(NotificationChannelBase):
    pass


class NotificationChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1, max_length=1024)
    severity_filter: Optional[List[str]] = None
    enabled: Optional[bool] = None


class NotificationChannelResponse(NotificationChannelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
