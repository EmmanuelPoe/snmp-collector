from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Database
    database_url: str = "postgresql://snmpuser:snmppass@postgres:5432/snmp_metrics"
    
    # SNMP Exporter
    snmp_exporter_url: str = "http://snmp-exporter:9116"
    
    # Prometheus configuration file path
    prometheus_config_path: str = "/app/prometheus_config/snmp.yml"
    
    # Collection settings
    default_collection_interval: int = 60  # seconds
    
    # API settings
    api_title: str = "SNMP Metrics Collector API"
    api_version: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
