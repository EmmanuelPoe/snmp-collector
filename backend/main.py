import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager

import httpx
from alert_evaluator import evaluation_loop
from audit import prune_old_entries
from auth import hash_password
from config import check_required_secrets, settings
from database import SessionLocal
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from models import User, UserRole
from prometheus_fastapi_instrumentator import Instrumentator
from rate_limit import limiter
from routers import (
    agents,
    audit_log,
    config,
    devices,
    internal,
    maintenance,
    metrics,
    notifications,
    prometheus,
    topology,
)
from routers.alerts import alerts_router, rules_router
from routers.auth import router as auth_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "service": "backend",
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def _setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


_setup_logging()
logger = logging.getLogger(__name__)


# Weekly, mirroring the manager's metrics retention loop.
_AUDIT_RETENTION_INTERVAL_S = 7 * 24 * 3600


async def audit_retention_loop():
    while True:
        try:
            db = SessionLocal()
            try:
                deleted = prune_old_entries(db, settings.audit_retention_days)
                if deleted:
                    logger.info("audit retention prune: %d rows deleted", deleted)
            finally:
                db.close()
        except Exception as exc:
            logger.warning("audit retention prune failed: %s", exc)
        await asyncio.sleep(_AUDIT_RETENTION_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_required_secrets()
    # Step 2.2: a dead Postgres must fail startup loudly (compose healthcheck +
    # restart policy handles boot-order retries), not defer errors to the first
    # request while /health reports healthy.
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            password = secrets.token_urlsafe(16)
            admin = User(
                email="admin@localhost",
                hashed_password=hash_password(password),
                role=UserRole.admin,
                force_password_change=True,
            )
            db.add(admin)
            db.commit()
            logger.warning(
                "Bootstrap admin created — login with admin@localhost / %s then change your password. "
                "This one-time password is not shown again.",
                password,
            )
    except OperationalError:
        logger.error("Postgres is unreachable at startup — aborting (database_url host: %s)", settings.postgres_host)
        raise
    finally:
        db.close()
    tasks = [asyncio.create_task(evaluation_loop()), asyncio.create_task(audit_retention_loop())]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API for collecting and managing SNMP metrics from network devices",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    # Step 1.6: only what the API actually uses — no PATCH/TRACE, no arbitrary
    # request headers.
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

Instrumentator().instrument(app).expose(app, endpoint="/internal/prometheus")

app.include_router(auth_router)
app.include_router(devices.router)
app.include_router(metrics.router)
app.include_router(config.router)
app.include_router(internal.router)
app.include_router(agents.router)
app.include_router(alerts_router)
app.include_router(rules_router)
app.include_router(notifications.router)
app.include_router(maintenance.router)
app.include_router(prometheus.router)
app.include_router(topology.router)
app.include_router(audit_log.router)


@app.get("/")
def root():
    return {"message": "SNMP Metrics Collector API", "version": settings.api_version}


@app.get("/health")
@app.get("/health/live")
def health_live():
    """Liveness: the process is up. /health stays as an alias (nginx proxies it)."""
    return {"status": "healthy", "service": "snmp-collector-api"}


@app.get("/health/ready")
def health_ready(response: Response):
    """Readiness (Step 2.3): Postgres is the hard dependency. The manager
    (metrics path) is reported but non-fatal — device CRUD/auth still work
    without it, and its own readiness is checked on its /health/ready."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unready", "postgres": f"unavailable: {exc.__class__.__name__}"}

    manager_status = "ok"
    try:
        httpx.get(f"{settings.manager_url}/health", timeout=2)
    except httpx.HTTPError:
        manager_status = "unreachable"
    return {"status": "ready", "postgres": "ok", "manager": manager_status}
