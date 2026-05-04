from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: Optional[str] = None
    duckdb_path: str = "/data/db/metrics.db"
    manager_url: str = "http://manager:8000"
    api_title: str = "SNMP Metrics Collector API"
    api_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = False

    def model_post_init(self, __context):
        if not self.database_url:
            self.database_url = (
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )


settings = Settings()
