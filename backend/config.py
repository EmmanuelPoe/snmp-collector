from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: Optional[str] = None
    manager_url: str = "http://manager:8000"
    api_title: str = "SNMP Metrics Collector API"
    api_version: str = "1.0.0"
    manager_api_key: str = ""
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8
    # Fernet key for encrypting SNMP credentials at rest. When empty, a stable key
    # is derived from jwt_secret (see crypto.py). Set a dedicated key in production.
    encryption_key: Optional[str] = None
    frontend_url: str = "http://localhost"
    # Dedicated bearer token for the Prometheus scrape endpoint. Empty disables
    # the endpoint (503) so it is never unintentionally exposed unauthenticated.
    prometheus_scrape_token: str = ""
    # Dynamic baseline anomaly detection (off by default to avoid surprise noise).
    baseline_anomaly_enabled: bool = False
    baseline_multiplier: float = 1.5
    baseline_min_samples: int = 100
    baseline_window_days: float = 7.0
    # Topology dependency suppression: when a device on a child's only path to the
    # topology root(s) is down, suppress the child's (collateral) alerts. Off by
    # default so it never changes alerting behaviour on upgrade without opt-in.
    topology_suppression_enabled: bool = False
    # Rate limiting + login lockout (Step 1.3 / plan Step 15). Limits use the
    # slowapi/limits string format ("N/minute"). The in-process limiter state is
    # per uvicorn worker; the DB-backed account lockout is the authoritative brake.
    rate_limit_enabled: bool = True
    login_rate_limit: str = "10/minute"
    walk_rate_limit: str = "6/minute"
    login_lockout_threshold: int = 10
    login_lockout_minutes: int = 15
    # Audit trail retention (Step 1.5): >1 year so annual reviews always have a
    # full window. Rows are pruned weekly by a background task.
    audit_retention_days: int = 400

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def model_post_init(self, __context):
        if not self.database_url:
            self.database_url = (
                f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )


settings = Settings()


# Secrets that ship as defaults/placeholders in config or .env.example. Starting
# with any of these means the deployment is using a publicly known secret.
_PLACEHOLDER_SECRETS = {
    "change-me-in-production",
    "replace-with-a-long-random-secret",
    "changeme",
    "change-me",
    "secret",
    "password",
    "replace-me",
    "your-secret-here",
}
_MIN_SECRET_LENGTH = 16


def _secret_problems(name: str, value: Optional[str]) -> list[str]:
    if not value:
        return [f"{name} is not set"]
    if value.strip().lower() in _PLACEHOLDER_SECRETS:
        return [f"{name} is set to a known placeholder/default value"]
    if len(value) < _MIN_SECRET_LENGTH:
        return [f"{name} must be at least {_MIN_SECRET_LENGTH} characters"]
    return []


def check_required_secrets() -> None:
    """Fail fast if any required secret is unset, a known placeholder, or too short.

    Called at application startup so an insecure deployment aborts with a clear
    message instead of silently running with a publicly known secret.
    """
    problems = _secret_problems("JWT_SECRET", settings.jwt_secret)
    problems += _secret_problems("MANAGER_API_KEY", settings.manager_api_key)
    # ENCRYPTION_KEY may be empty (a key is derived from JWT_SECRET); only reject a
    # placeholder value. Its Fernet format is validated on first use in crypto.py.
    if settings.encryption_key and settings.encryption_key.strip().lower() in _PLACEHOLDER_SECRETS:
        problems.append("ENCRYPTION_KEY is set to a known placeholder value")
    if problems:
        raise RuntimeError(
            "Insecure secret configuration — refusing to start:\n  - "
            + "\n  - ".join(problems)
            + "\nSet strong, unique values for these (see .env.example)."
        )
