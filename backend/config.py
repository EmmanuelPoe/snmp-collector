from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Database Configuration
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    
    # Constructed URL (can be overridden by environment variable DATABASE_URL)
    database_url: Optional[str] = None
    
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

    def model_post_init(self, __context):
        if not self.database_url:
            self.database_url = f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
