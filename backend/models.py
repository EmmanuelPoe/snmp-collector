from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
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
    snmp_modules = Column(JSONB, default=["if_mib"]) # List of modules to use
    device_type = Column(String(50))  # router, switch, etc.
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    metrics = relationship("SNMPMetric", back_populates="device", cascade="all, delete-orphan")
    if_mib_metrics = relationship("IfMibMetric", back_populates="device", cascade="all, delete-orphan")
    schedules = relationship("CollectionSchedule", back_populates="device", cascade="all, delete-orphan")


class SNMPMetric(Base):
    """Generic Time-series SNMP metrics storage (EAV Model)"""
    __tablename__ = "snmp_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    module = Column(String(50), nullable=False, index=True, server_default='if_mib') 
    interface_name = Column(String(255), index=True)
    interface_index = Column(Integer)
    oid = Column(String(255), nullable=False, index=True)
    oid_name = Column(String(255))
    value = Column(Float)
    value_type = Column(String(50))
    
    # Relationships
    device = relationship("Device", back_populates="metrics")


class IfMibMetric(Base):
    """
    Dedicated Time-series table for Interface MIB metrics.
    Stores one row per interface per timestamp (Wide Model).
    """
    __tablename__ = "if_mib_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    interface_name = Column(String(255), index=True)
    interface_index = Column(Integer)
    
    # Standard IF-MIB Metrics
    if_admin_status = Column(Integer)
    if_oper_status = Column(Integer)
    if_in_octets = Column(BigInteger)
    if_out_octets = Column(BigInteger)
    if_in_errors = Column(Integer)
    if_out_errors = Column(Integer)
    if_in_discards = Column(Integer)
    if_out_discards = Column(Integer)
    if_in_ucast_pkts = Column(BigInteger)
    if_out_ucast_pkts = Column(BigInteger)
    if_speed = Column(BigInteger)
    if_mtu = Column(Integer)
    
    # HC (64-bit) Counters
    if_hc_in_octets = Column(BigInteger)
    if_hc_out_octets = Column(BigInteger)
    if_hc_in_ucast_pkts = Column(BigInteger)
    if_hc_out_ucast_pkts = Column(BigInteger)
    
    # Relationships
    device = relationship("Device", back_populates="if_mib_metrics")


class CollectionConfig(Base):
    """SNMP OID collection configuration"""
    __tablename__ = "collection_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    oid = Column(String(255), unique=True, nullable=False, index=True)
    oid_name = Column(String(255), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CollectionSchedule(Base):
    """Collection schedule per device"""
    __tablename__ = "collection_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), unique=True, nullable=False)
    interval_seconds = Column(Integer, default=60)
    enabled = Column(Boolean, default=True)
    last_collection = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="schedules")
