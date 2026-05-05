from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    snmp_version = Column(String(10), default="2c")
    snmp_community = Column(String(255), default="public")
    snmp_port = Column(Integer, default=161)
    snmp_modules = Column(JSON, default=["if_mib"])
    device_type = Column(String(50))
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    username = Column(String(255), nullable=True)
    auth_protocol = Column(String(50), nullable=True)
    auth_password = Column(String(255), nullable=True)
    priv_protocol = Column(String(50), nullable=True)
    priv_password = Column(String(255), nullable=True)
    assigned_agent_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CollectionConfig(Base):
    __tablename__ = "collection_configs"

    id = Column(Integer, primary_key=True, index=True)
    oid = Column(String(255), unique=True, nullable=False, index=True)
    oid_name = Column(String(255), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
