import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

import config
from db import get_db, close_db, purge_old_metrics
from routers import registration, ingest, metrics, slots, commands

logger = logging.getLogger(__name__)

_RETENTION_INTERVAL_SECONDS = 7 * 24 * 3600  # weekly


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "time": self.formatTime(record),
            "level": record.levelname,
            "service": "manager",
            "logger": record.name,
            "message": record.getMessage(),
        })


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


@app.get("/health")
def health():
    return {"status": "ok"}
