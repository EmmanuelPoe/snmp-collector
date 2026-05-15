import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from db import get_db, close_db
from routers import registration, ingest, metrics


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    yield
    close_db()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

Instrumentator().instrument(app).expose(app)

app.include_router(registration.router)
app.include_router(ingest.router)
app.include_router(metrics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
