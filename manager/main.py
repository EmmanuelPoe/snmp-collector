from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import get_db, close_db
from routers import registration, devices, ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    yield
    close_db()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(registration.router)
app.include_router(devices.router)
app.include_router(ingest.router)


@app.get("/health")
def health():
    return {"status": "ok"}
