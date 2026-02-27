"""
Integration tests for API2: Session storage endpoints.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Use in-memory SQLite for tests
os.environ["DATABASE_URL"] = "sqlite:///./test_session.db"

from backend.models.database import create_tables  # noqa: E402
from backend.main import app  # noqa: E402

create_tables()
client = TestClient(app)


# ── Start session ────────────────────────────────────────────

class TestStartSession:
    def test_start_session_returns_session_id(self):
        resp = client.post("/api/session/start", json={
            "username": "test_user_1",
            "instrument": "erhu",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "user_id" in data
        assert len(data["session_id"]) == 16

    def test_same_user_second_session(self):
        client.post("/api/session/start", json={"username": "test_user_2"})
        resp = client.post("/api/session/start", json={"username": "test_user_2"})
        assert resp.status_code == 200


# ── Save result ──────────────────────────────────────────────

class TestSaveResult:
    def test_save_result_to_session(self):
        # Start session
        start_resp = client.post("/api/session/start", json={"username": "test_user_3"})
        session_id = start_resp.json()["session_id"]

        # Save a result
        resp = client.post("/api/session/result", json={
            "session_id": session_id,
            "result": {
                "exercise_type": "long_tone",
                "duration_s": 10.0,
                "overall_score": 85.0,
                "pitch_score": 90.0,
                "stability_score": 80.0,
                "rhythm_score": 85.0,
            },
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"

    def test_save_result_missing_session(self):
        resp = client.post("/api/session/result", json={
            "session_id": "nonexistent",
            "result": {
                "exercise_type": "long_tone",
                "duration_s": 5.0,
                "overall_score": 70.0,
            },
        })
        assert resp.status_code == 404


# ── End session ──────────────────────────────────────────────

class TestEndSession:
    def test_end_session(self):
        # Start
        start_resp = client.post("/api/session/start", json={"username": "test_user_4"})
        session_id = start_resp.json()["session_id"]

        # Save a result
        client.post("/api/session/result", json={
            "session_id": session_id,
            "result": {
                "exercise_type": "scale",
                "duration_s": 15.0,
                "overall_score": 75.0,
            },
        })

        # End
        resp = client.post("/api/session/end", json={"session_id": session_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["exercise_count"] == 1
        assert data["overall_score"] == 75.0

    def test_end_nonexistent_session(self):
        resp = client.post("/api/session/end", json={"session_id": "fake123"})
        assert resp.status_code == 404


# ── Progress ─────────────────────────────────────────────────

class TestProgress:
    def test_get_progress(self):
        # Start session + save result to create progress data
        start_resp = client.post("/api/session/start", json={"username": "test_user_5"})
        session_id = start_resp.json()["session_id"]
        client.post("/api/session/result", json={
            "session_id": session_id,
            "result": {
                "exercise_type": "long_tone",
                "duration_s": 10.0,
                "overall_score": 90.0,
                "pitch_score": 95.0,
                "stability_score": 85.0,
            },
        })

        resp = client.get("/api/progress/test_user_5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "test_user_5"
        assert data["total_sessions"] >= 1
        assert len(data["skills"]) >= 1

    def test_progress_user_not_found(self):
        resp = client.get("/api/progress/nonexistent_user")
        assert resp.status_code == 404
