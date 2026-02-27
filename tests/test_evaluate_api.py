"""
Integration tests for API1: POST /api/evaluate endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────

def make_request_body(
    exercise_type: str = "long_tone",
    freq: float = 440.0,
    duration: float = 2.0,
    fps: int = 50,
    target_frequency: float | None = 440.0,
) -> dict:
    frames = [
        {"time": i / fps, "frequency": freq, "confidence": 0.9}
        for i in range(int(duration * fps))
    ]
    body = {
        "exercise_type": exercise_type,
        "frames": frames,
        "duration": duration,
    }
    if target_frequency is not None:
        body["target_frequency"] = target_frequency
    return body


# ── Successful evaluation ────────────────────────────────────

class TestSuccessfulEvaluation:
    def test_long_tone_returns_200(self):
        body = make_request_body()
        resp = client.post("/api/evaluate", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert "overall_score" in data
        assert "pitch_score" in data
        assert "stability_score" in data
        assert "textual_feedback" in data
        assert 0 <= data["overall_score"] <= 100

    def test_perfect_pitch_high_score(self):
        body = make_request_body(freq=440.0, target_frequency=440.0)
        resp = client.post("/api/evaluate", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] >= 90
        assert data["stability_detail"] is not None

    def test_with_reference_curve(self):
        body = make_request_body()
        body["reference_curve"] = [
            {"time": i / 50, "frequency": 440.0}
            for i in range(100)
        ]
        resp = client.post("/api/evaluate", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["dtw_detail"] is not None
        assert data["dtw_detail"]["pitch_error_mean"] >= 0


# ── Validation errors ────────────────────────────────────────

class TestValidation:
    def test_rejects_duration_over_60s(self):
        body = make_request_body(duration=61.0)
        resp = client.post("/api/evaluate", json=body)
        assert resp.status_code == 422  # Pydantic validation (le=60)

    def test_rejects_empty_frames(self):
        body = {
            "exercise_type": "long_tone",
            "frames": [],
            "duration": 1.0,
        }
        resp = client.post("/api/evaluate", json=body)
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_rejects_missing_exercise_type(self):
        body = {
            "frames": [{"time": 0, "frequency": 440, "confidence": 0.9}],
            "duration": 1.0,
        }
        resp = client.post("/api/evaluate", json=body)
        assert resp.status_code == 422


# ── Response shape ───────────────────────────────────────────

class TestResponseShape:
    def test_all_score_fields_present(self):
        body = make_request_body()
        resp = client.post("/api/evaluate", json=body)
        data = resp.json()

        required_fields = [
            "overall_score", "pitch_score", "stability_score",
            "slide_score", "rhythm_score", "recommended_training_type",
            "textual_feedback",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_stability_detail_shape(self):
        body = make_request_body()
        resp = client.post("/api/evaluate", json=body)
        data = resp.json()

        sd = data["stability_detail"]
        assert sd is not None
        assert "stability_score" in sd
        assert "mean_deviation_cents" in sd
        assert "variance_cents" in sd
        assert "unstable_ranges" in sd
