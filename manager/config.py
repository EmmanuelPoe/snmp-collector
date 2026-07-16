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
    metrics_retention_days: int = 90
    # Step 1.7 grace mode: false accepts the shared MANAGER_API_KEY on
    # agent-facing routes (with a warning) so pre-1.7 agents keep working.
    # Flip to true once every agent holds a per-agent credential.
    agent_auth_enforce: bool = False

    model_config = {"env_file": ".env"}

settings = Settings()

# Secrets that ship as defaults/placeholders; starting with any means the
# deployment is using a publicly known secret.
_PLACEHOLDER_SECRETS = {
    "change-me-in-production",
    "replace-with-a-long-random-secret",
    "changeme",
    "change-me",
    "secret",
    "password",
}
_MIN_SECRET_LENGTH = 16


def check_required_secrets() -> None:
    """Fail fast at startup if MANAGER_API_KEY is unset, a placeholder, or too short."""
    value = settings.manager_api_key
    problem = None
    if not value:
        problem = "MANAGER_API_KEY is not set"
    elif value.strip().lower() in _PLACEHOLDER_SECRETS:
        problem = "MANAGER_API_KEY is set to a known placeholder/default value"
    elif len(value) < _MIN_SECRET_LENGTH:
        problem = f"MANAGER_API_KEY must be at least {_MIN_SECRET_LENGTH} characters"
    if problem:
        raise RuntimeError(
            f"Insecure secret configuration — refusing to start: {problem}. "
            "Set a strong, unique value (see .env.example)."
        )
