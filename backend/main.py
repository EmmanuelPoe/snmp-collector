from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from contextlib import asynccontextmanager

from config import settings
from routers import devices, metrics, config
from services.collector import run_scheduled_collection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("Starting SNMP Collector API")
    
    # Start background collection task
    collection_task = asyncio.create_task(run_scheduled_collection())
    logger.info("Background collection task started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down SNMP Collector API")
    collection_task.cancel()
    try:
        await collection_task
    except asyncio.CancelledError:
        logger.info("Background collection task cancelled")


# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API for collecting and managing SNMP metrics from network devices",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(devices.router)
app.include_router(metrics.router)
app.include_router(config.router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "SNMP Metrics Collector API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "snmp-collector-api"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
