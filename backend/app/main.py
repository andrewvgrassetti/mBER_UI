"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .routers import jobs, system, websocket
from .services.job_service import start_queue_worker, stop_queue_worker
from .services.keepalive import shutdown_keepalive


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    await start_queue_worker()
    yield
    await stop_queue_worker()
    shutdown_keepalive()


app = FastAPI(
    title="mBER UI API",
    description="Backend API for the mBER VHH nanobody binder design tool",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(jobs.router)
app.include_router(system.router)
app.include_router(websocket.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
