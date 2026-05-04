from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import settings
from routers import devices, metrics, config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API for collecting and managing SNMP metrics from network devices",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router)
app.include_router(metrics.router)
app.include_router(config.router)


@app.get("/")
def root():
    return {"message": "SNMP Metrics Collector API", "version": settings.api_version}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "snmp-collector-api"}
