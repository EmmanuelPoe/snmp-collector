from pydantic import BaseModel, Field, IPvAnyAddress
from datetime import datetime
from typing import Optional, List


# ===== Device Schemas =====

class DeviceBase(BaseModel):
    """Base device schema"""
    name: str = Field(..., min_length=1, max_length=255)
    ip_address: str
    snmp_version: str = Field(default="2c", pattern="^(1|2c|3)$")
    snmp_community: str = Field(default="public", min_length=1)
    snmp_port: int = Field(default=161, ge=1, le=65535)
    device_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    enabled: bool = True


class DeviceCreate(DeviceBase):
    """Schema for creating a device"""
    pass


class DeviceUpdate(BaseModel):
    """Schema for updating a device"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    ip_address: Optional[str] = None
    snmp_version: Optional[str] = Field(None, pattern="^(1|2c|3)$")
    snmp_community: Optional[str] = Field(None, min_length=1)
    snmp_port: Optional[int] = Field(None, ge=1, le=65535)
    device_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    enabled: Optional[bool] = None


class DeviceResponse(DeviceBase):
    """Schema for device response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ===== Metric Schemas =====

class MetricBase(BaseModel):
    """Base metric schema"""
    device_id: int
    interface_name: Optional[str] = None
    interface_index: Optional[int] = None
    oid: str
    oid_name: Optional[str] = None
    value: Optional[float] = None
    value_type: Optional[str] = None


class MetricResponse(MetricBase):
    """Schema for metric response"""
    id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True


class MetricQuery(BaseModel):
    """Schema for querying metrics"""
    device_id: Optional[int] = None
    interface_name: Optional[str] = None
    oid: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=1000, ge=1, le=10000)


# ===== Collection Config Schemas =====

class CollectionConfigBase(BaseModel):
    """Base collection config schema"""
    oid: str = Field(..., min_length=1)
    oid_name: str = Field(..., min_length=1)
    description: Optional[str] = None
    enabled: bool = True


class CollectionConfigCreate(CollectionConfigBase):
    """Schema for creating collection config"""
    pass


class CollectionConfigResponse(CollectionConfigBase):
    """Schema for collection config response"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ===== Schedule Schemas =====

class ScheduleBase(BaseModel):
    """Base schedule schema"""
    interval_seconds: int = Field(default=60, ge=10, le=86400)  # 10 seconds to 24 hours
    enabled: bool = True


class ScheduleCreate(ScheduleBase):
    """Schema for creating schedule"""
    device_id: int


class ScheduleUpdate(BaseModel):
    """Schema for updating schedule"""
    interval_seconds: Optional[int] = Field(None, ge=10, le=86400)
    enabled: Optional[bool] = None


class ScheduleResponse(ScheduleBase):
    """Schema for schedule response"""
    id: int
    device_id: int
    last_collection: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ===== Interface Schemas =====

class InterfaceInfo(BaseModel):
    """Interface information"""
    interface_name: str
    interface_index: int
    status: Optional[str] = None  # up, down, testing, etc.


class DeviceMetricsSummary(BaseModel):
    """Summary of device metrics"""
    device: DeviceResponse
    interfaces: List[InterfaceInfo]
    latest_metrics: List[MetricResponse]
