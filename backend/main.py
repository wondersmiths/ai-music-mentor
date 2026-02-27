"""
Application entry point — assembles the FastAPI app with all routers,
middleware, CORS, and error handling.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure project root is on sys.path for ai.* imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.config import settings  # noqa: E402
from backend.logging_setup import setup_logging  # noqa: E402
from backend.middleware.rate_limit import RateLimitMiddleware  # noqa: E402
from backend.routers import analyze, evaluate, health, practice, score, session  # noqa: E402

# ── Logging ──────────────────────────────────────────────────

setup_logging()
logger = logging.getLogger("backend")

# ── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="AI Music Mentor",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

# ── CORS ─────────────────────────────────────────────────────

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Rate Limiting ─────────────────────────────────────────────

if settings.ENVIRONMENT == "production":
    app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)

# ── Routers ──────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(evaluate.router)
app.include_router(score.router)
app.include_router(practice.router)
app.include_router(session.router)

# ── Middleware: request logging ──────────────────────────────


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info(
        "%s %s → %d (%.0f ms)",
        request.method, request.url.path,
        response.status_code, elapsed,
    )
    return response


# ── Global exception handler ────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Startup log ─────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    # Create database tables if they don't exist
    from backend.models.database import create_tables
    create_tables()

    logger.info(
        "Starting AI Music Mentor v%s [%s] on :%d",
        settings.APP_VERSION, settings.ENVIRONMENT, settings.PORT,
    )


# ── Dev entrypoint ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
