from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    manager_api_key: str
    db_path: str = "/data/db/metrics.db"
    registry_path: str = "/data/registry/registry.json"
    slots_path: str = "/data/registry/slots.json"
    slot_expiry_hours: int = 24
    manager_public_url: str = "http://localhost:8001"
    dead_letter_path: str = "/data/dead-letter"
    backend_url: str = "http://backend:8000"

    model_config = {"env_file": ".env"}

settings = Settings()
