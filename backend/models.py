import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Enum, Float
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
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CollectionConfig(Base):
    __tablename__ = "collection_configs"

    id = Column(Integer, primary_key=True, index=True)
    oid = Column(String(255), unique=True, nullable=False, index=True)
    oid_name = Column(String(255), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    # Core OIDs the metrics/alerting pipeline depends on. Cannot be disabled or
    # deleted via the API; reseeded by migration 013.
    required = Column(Boolean, default=False, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserRole(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.viewer)
    is_active = Column(Boolean, default=True)
    force_password_change = Column(Boolean, nullable=False, server_default="true", default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AlertType(str, enum.Enum):
    device_unreachable = "device_unreachable"
    interface_down = "interface_down"
    bandwidth_threshold = "bandwidth_threshold"
    agent_offline = "agent_offline"
    error_rate = "error_rate"


class AlertStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class AlertSeverity(str, enum.Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, nullable=True)
    agent_id = Column(String(255), nullable=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    severity = Column(Enum(AlertSeverity), nullable=False,
                      default=AlertSeverity.warning, server_default="warning")
    message = Column(Text, nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.open, server_default="open")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, nullable=False, unique=True)
    bandwidth_in_pct = Column(Float, nullable=True)
    bandwidth_out_pct = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)


class NotificationChannelType(str, enum.Enum):
    slack = "slack"
    webhook = "webhook"


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(Enum(NotificationChannelType), nullable=False)
    url = Column(String(1024), nullable=False)
    # Severities that trigger this channel. Empty list = all severities.
    severity_filter = Column(JSON, default=list)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
