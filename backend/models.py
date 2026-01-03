from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Device(Base):
    """Network device (router/switch) model"""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)  # Supports IPv4 and IPv6
    snmp_version = Column(String(10), default="2c")  # 1, 2c, or 3
    snmp_community = Column(String(255), default="public")
    snmp_port = Column(Integer, default=161)
    device_type = Column(String(50))  # router, switch, etc.
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    metrics = relationship("SNMPMetric", back_populates="device", cascade="all, delete-orphan")
    schedules = relationship("CollectionSchedule", back_populates="device", cascade="all, delete-orphan")


class SNMPMetric(Base):
    """Time-series SNMP metrics storage (TimescaleDB hypertable)"""
    __tablename__ = "snmp_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    interface_name = Column(String(255), index=True)  # e.g., "GigabitEthernet0/1"
    interface_index = Column(Integer)  # ifIndex
    oid = Column(String(255), nullable=False, index=True)
    oid_name = Column(String(255))  # Human-readable name (e.g., "ifOperStatus")
    value = Column(Float)
    value_type = Column(String(50))  # gauge, counter, etc.
    
    # Relationships
    device = relationship("Device", back_populates="metrics")


class CollectionConfig(Base):
    """SNMP OID collection configuration"""
    __tablename__ = "collection_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    oid = Column(String(255), unique=True, nullable=False, index=True)
    oid_name = Column(String(255), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Common OIDs
    # ifOperStatus: 1.3.6.1.2.1.2.2.1.8
    # ifInOctets: 1.3.6.1.2.1.2.2.1.10
    # ifOutOctets: 1.3.6.1.2.1.2.2.1.16
    # ifInUcastPkts: 1.3.6.1.2.1.2.2.1.11
    # ifOutUcastPkts: 1.3.6.1.2.1.2.2.1.17


class CollectionSchedule(Base):
    """Collection schedule per device"""
    __tablename__ = "collection_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False)
    interval_seconds = Column(Integer, default=60)  # Collection interval in seconds
    enabled = Column(Boolean, default=True)
    last_collection = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="schedules")
