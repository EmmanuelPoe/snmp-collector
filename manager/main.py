import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

import config
import db as db_mod
import metrics as platform_metrics
from db import close_db, get_db, purge_old_metrics
from fastapi import FastAPI, Response, status
from logging_json import CorrelationMiddleware, configure_logging, get_logger
from prometheus_fastapi_instrumentator import Instrumentator
from routers import backup, commands, ingest, metrics, registration, slots

configure_logging("manager")
logger = get_logger(__name__)

_RETENTION_INTERVAL_SECONDS = 7 * 24 * 3600  # weekly
_METRICS_REFRESH_SECONDS = 60
_BACKUP_SUFFIXES = (".dump", ".db")


async def _retention_loop():
    while True:
        try:
            result = await purge_old_metrics(config.settings.metrics_retention_days)
            if result["polls_deleted"] or result["traps_deleted"]:
                logger.info("retention purge: %s", result)
        except Exception as exc:
            logger.warning("retention purge failed: %s", exc)
        await asyncio.sleep(_RETENTION_INTERVAL_SECONDS)


def _newest_backup_mtime() -> float | None:
    try:
        mtimes = [
            p.stat().st_mtime
            for p in Path(config.settings.backup_dir).iterdir()
            if p.is_file() and p.suffix in _BACKUP_SUFFIXES
        ]
    except OSError:
        return None
    return max(mtimes) if mtimes else None


async def _metrics_refresh_loop():
    """Keep the size/age gauges fresh even when no ingest is happening."""
    while True:
        try:
            platform_metrics.duckdb_file_bytes.set(Path(config.settings.db_path).stat().st_size)
        except OSError:
            pass
        newest = _newest_backup_mtime()
        if newest is not None:
            platform_metrics.backup_age_seconds.set(time.time() - newest)
        await asyncio.sleep(_METRICS_REFRESH_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.check_required_secrets()
    get_db()
    tasks = [asyncio.create_task(_retention_loop()), asyncio.create_task(_metrics_refresh_loop())]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    close_db()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

# Adopt/mint a correlation id per request so an agent's upload can be followed
# from the agent's log through the manager's (Step 5.1).
app.add_middleware(CorrelationMiddleware)

Instrumentator().instrument(app).expose(app)

app.include_router(registration.router)
app.include_router(ingest.router)
app.include_router(metrics.router)
app.include_router(slots.router)
app.include_router(commands.router)
app.include_router(backup.router)


@app.get("/health")
@app.get("/health/live")
def health():
    """Liveness: the process is up. /health stays for existing probes."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(response: Response):
    """Readiness (Step 2.3): DuckDB answers through the write lock (so a
    saturated queue reads as unready, which is the honest signal) and the
    registry backend is reachable."""
    try:
        await db_mod.query("SELECT 1")
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unready", "duckdb": f"unavailable: {exc.__class__.__name__}"}

    from registry import DbAgentRegistry, registry

    registry_status = "ok"
    if isinstance(registry, DbAgentRegistry):
        try:
            from sqlalchemy import text

            with registry._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unready", "duckdb": "ok", "registry": f"unavailable: {exc.__class__.__name__}"}

    return {"status": "ready", "duckdb": "ok", "registry": registry_status, "write_queue": db_mod.write_queue_depth()}
