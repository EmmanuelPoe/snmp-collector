import asyncio
import json
import logging
from contextlib import asynccontextmanager

import config
import db as db_mod
from db import close_db, get_db, purge_old_metrics
from fastapi import FastAPI, Response, status
from prometheus_fastapi_instrumentator import Instrumentator
from routers import backup, commands, ingest, metrics, registration, slots

logger = logging.getLogger(__name__)

_RETENTION_INTERVAL_SECONDS = 7 * 24 * 3600  # weekly


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "service": "manager",
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def _setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


_setup_logging()


async def _retention_loop():
    while True:
        try:
            result = await purge_old_metrics(config.settings.metrics_retention_days)
            if result["polls_deleted"] or result["traps_deleted"]:
                logger.info("retention purge: %s", result)
        except Exception as exc:
            logger.warning("retention purge failed: %s", exc)
        await asyncio.sleep(_RETENTION_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.check_required_secrets()
    get_db()
    task = asyncio.create_task(_retention_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    close_db()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

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
