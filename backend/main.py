import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.exc import OperationalError

from alert_evaluator import evaluation_loop
from auth import hash_password
from config import settings
from database import SessionLocal
from models import User, UserRole
from routers import agents, config, devices, internal, metrics, notifications
from routers.alerts import alerts_router, rules_router
from routers.auth import router as auth_router


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "time": self.formatTime(record),
            "level": record.levelname,
            "service": "backend",
            "logger": record.name,
            "message": record.getMessage(),
        })


def _setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


_setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                email="admin@localhost",
                hashed_password=hash_password("changeme"),
                role=UserRole.admin,
                force_password_change=True,
            )
            db.add(admin)
            db.commit()
            logger.warning("Bootstrap admin created — login with admin@localhost / changeme and change your password")
    except OperationalError:
        pass
    finally:
        db.close()
    task = asyncio.create_task(evaluation_loop())
    yield
    task.cancel()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/")
def root():
    return {"message": "SNMP Metrics Collector API", "version": settings.api_version}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "snmp-collector-api"}
