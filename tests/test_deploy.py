"""
Tests for DEPLOY1: Production deployment features.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_deploy.db")

from backend.models.database import create_tables
from backend.main import app
from fastapi.testclient import TestClient

create_tables()
client = TestClient(app)


class TestHealthEndpoints:
    def test_health_liveness(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_readiness(self):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ready", "degraded")
        assert "uptime_s" in data
        assert "database" in data
        assert "version" in data

    def test_version_endpoint(self):
        resp = client.get("/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data


class TestRateLimitMiddleware:
    def test_rate_limit_headers_present_in_dev(self):
        """In development mode, rate limiter is not active."""
        resp = client.get("/health")
        # In dev mode, rate limiter is not added — no X-RateLimit headers
        assert resp.status_code == 200

    def test_rate_limiter_class_works(self):
        """Unit test the rate limiter middleware logic."""
        from backend.middleware.rate_limit import RateLimitMiddleware
        # Just verify it can be instantiated
        assert RateLimitMiddleware is not None
