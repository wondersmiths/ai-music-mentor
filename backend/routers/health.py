"""
Health check and version endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.schemas.analysis import HealthResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health():
    """Liveness probe for Railway / load balancers."""
    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
    )


@router.get("/version")
def version():
    """Return the application version."""
    return {"version": settings.APP_VERSION}
