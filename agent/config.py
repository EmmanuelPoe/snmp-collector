import os
import socket
from pathlib import Path

from pydantic_settings import BaseSettings


# Docker/compose secrets (Step 4.4): load <NAME> from <NAME>_FILE when set, so
# the shared key can come from a root-owned file rather than the environment.
def _hydrate_file_secrets(*names: str) -> None:
    for name in names:
        if os.environ.get(name):
            continue
        path = os.environ.get(f"{name}_FILE")
        if path and Path(path).is_file():
            os.environ[name] = Path(path).read_text().strip()


_hydrate_file_secrets("MANAGER_API_KEY")


class Settings(BaseSettings):
    manager_url: str
    # Only needed for the /register bootstrap path (dev compose). Agents
    # enrolled with a claim token never hold the shared key (Step 1.7) — they
    # authenticate with the per-agent secret issued at claim.
    manager_api_key: str = ""
    agent_hostname: str = socket.gethostname()
    agent_ip: str = ""
    claim_token: str = ""
    poll_interval_seconds: int = 60
    upload_max_rows: int = 500
    upload_max_age_seconds: int = 60
    retry_max_age_seconds: int = 3600
    queue_path: str = "/data/queue"
    agent_id_path: str = "/data/agent_id"
    agent_secret_path: str = "/data/agent_secret"
    trap_enabled: bool = False
    trap_listen_port: int = 162
    trap_community: str = "public"

    model_config = {"env_file": ".env"}


settings = Settings()
