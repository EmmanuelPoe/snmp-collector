from pydantic_settings import BaseSettings
import socket


class Settings(BaseSettings):
    manager_url: str
    manager_api_key: str
    agent_hostname: str = socket.gethostname()
    agent_ip: str = ""
    claim_token: str = ""
    poll_interval_seconds: int = 60
    upload_max_rows: int = 500
    upload_max_age_seconds: int = 60
    retry_max_age_seconds: int = 3600
    queue_path: str = "/data/queue"
    agent_id_path: str = "/data/agent_id"

    model_config = {"env_file": ".env"}


settings = Settings()
