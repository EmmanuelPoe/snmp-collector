"""Per-agent credential storage and selection (Step 1.7).

The manager issues a per-agent secret exactly once at register/claim; it is
persisted next to the agent-ID file with mode 0600 and sent as
`Bearer <agent_id>:<secret>` on every subsequent call. Agents enrolled before
Step 1.7 have no stored secret and fall back to the shared MANAGER_API_KEY,
which works while the manager runs in grace mode (AGENT_AUTH_ENFORCE=false).
"""
import os
from pathlib import Path

import config


def save_secret(secret: str) -> None:
    path = Path(config.settings.agent_secret_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(secret)


def load_secret() -> str | None:
    path = Path(config.settings.agent_secret_path)
    if path.exists():
        return path.read_text().strip() or None
    return None


def auth_token(agent_id: str | None, secret: str | None) -> str:
    if agent_id and secret:
        return f"{agent_id}:{secret}"
    return config.settings.manager_api_key
