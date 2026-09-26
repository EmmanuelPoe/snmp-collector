import hmac
import logging

import config
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from registry import registry

logger = logging.getLogger(__name__)

_bearer = HTTPBearer()

# Sentinel identity returned by require_agent_auth when the shared key is used
# in grace mode — acts as any agent, so same_agent checks pass.
SHARED_KEY_IDENTITY = "*"


def require_api_key(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    if not hmac.compare_digest(credentials.credentials, config.settings.manager_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return credentials.credentials


def require_agent_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> str:
    """Per-agent credential (Step 1.7): `Bearer <agent_id>:<secret>`, verified
    against the stored hash in constant time. Returns the authenticated
    agent_id. Deregistering an agent kills its credential immediately.

    Grace mode (AGENT_AUTH_ENFORCE=false, the one-release default): the shared
    MANAGER_API_KEY is still accepted with a warning so pre-1.7 agents keep
    working; flip AGENT_AUTH_ENFORCE=true to retire it on agent routes.
    """
    token = credentials.credentials
    if ":" in token:
        agent_id, secret = token.split(":", 1)
        info = registry.get(agent_id)
        # Unknown agent (registry reset/migrated/restored older than enrollment)
        # → 404 so the agent re-registers (Step 2.1 self-heal). A *known* agent
        # presenting a bad secret is a real auth failure → 401, no auto-heal.
        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unknown agent — re-registration required",
            )
        if info.verify_secret(secret):
            return agent_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credential",
        )
    if hmac.compare_digest(token, config.settings.manager_api_key):
        if config.settings.agent_auth_enforce:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Shared API key is not accepted on agent routes (AGENT_AUTH_ENFORCE)",
            )
        logger.warning(
            "agent route authenticated with the shared MANAGER_API_KEY — "
            "re-enroll the agent for a per-agent credential (grace mode; "
            "AGENT_AUTH_ENFORCE=true retires this)"
        )
        return SHARED_KEY_IDENTITY
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid agent credential",
    )


def ensure_same_agent(identity: str, agent_id: str) -> None:
    """An authenticated agent may only act as itself."""
    if identity != SHARED_KEY_IDENTITY and identity != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent credential does not match target agent",
        )
