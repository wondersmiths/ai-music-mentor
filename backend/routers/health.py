"""
Health check and version endpoints.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import get_db
from backend.schemas.analysis import HealthResponse

router = APIRouter(tags=["meta"])

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
def health():
    """Liveness probe for Railway / load balancers."""
    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
    )


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    """Readiness probe — checks database connectivity."""
    try:
        db.execute("SELECT 1")  # type: ignore[arg-type]
        db_ok = True
    except Exception:
        db_ok = False

    status = "ready" if db_ok else "degraded"
    return {
        "status": status,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_s": round(time.time() - _start_time, 1),
        "database": "ok" if db_ok else "error",
    }


@router.get("/version")
def version():
    """Return the application version."""
    return {"version": settings.APP_VERSION}


@router.get("/instruments")
def instruments():
    """List supported instruments with their display names."""
    from ai.instruments.profiles import INSTRUMENT_PROFILES
    return {
        "instruments": [
            {
                "name": p.name,
                "display_name": p.display_name,
                "family": p.family,
                "default_tonic": p.default_tonic,
                "freq_range": [p.freq_min, p.freq_max],
            }
            for p in INSTRUMENT_PROFILES.values()
        ],
    }
