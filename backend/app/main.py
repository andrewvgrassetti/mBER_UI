"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .routers import jobs, system, websocket

app = FastAPI(
    title="mBER UI API",
    description="Backend API for the mBER VHH nanobody binder design tool",
    version="0.1.0",
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
