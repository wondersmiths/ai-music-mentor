"""
Tests for P1: Progression Engine.
"""

from __future__ import annotations

import pytest

from ai.progression.engine import (
    ProgressionRecommendation,
    SkillSnapshot,
    recommend,
)


class TestNoSkillData:
    def test_first_time_user(self):
        rec = recommend([], total_sessions=0)
        assert rec.recommended_exercise == "long_tone"
        assert rec.difficulty == "beginner"
        assert "Welcome" in rec.message

    def test_returning_user_no_skills(self):
        rec = recommend([], total_sessions=3)
        assert rec.recommended_exercise == "long_tone"
        assert rec.difficulty == "beginner"


class TestWeakAreas:
    def test_weak_stability_recommends_long_tone(self):
        skills = [
            SkillSnapshot("pitch", 75.0, 5),
            SkillSnapshot("stability", 40.0, 3),
            SkillSnapshot("rhythm", 70.0, 4),
        ]
        rec = recommend(skills)
        assert rec.recommended_exercise == "long_tone"
        assert "stability" in rec.focus_areas
        # avg = 61.67 → intermediate, but stability is still a weak area
        assert rec.difficulty == "intermediate"

    def test_weak_pitch_recommends_scale(self):
        skills = [
            SkillSnapshot("pitch", 45.0, 2),
            SkillSnapshot("stability", 80.0, 8),
            SkillSnapshot("rhythm", 75.0, 6),
        ]
        rec = recommend(skills)
        assert rec.recommended_exercise == "scale"
        assert "pitch" in rec.focus_areas

    def test_weak_rhythm_recommends_drill(self):
        skills = [
            SkillSnapshot("pitch", 70.0, 5),
            SkillSnapshot("stability", 75.0, 5),
            SkillSnapshot("rhythm", 50.0, 3),
        ]
        rec = recommend(skills)
        assert rec.recommended_exercise == "rhythm_drill"
        assert "rhythm" in rec.focus_areas

    def test_multiple_weak_areas_picks_weakest(self):
        skills = [
            SkillSnapshot("pitch", 55.0, 5),
            SkillSnapshot("stability", 30.0, 2),
            SkillSnapshot("rhythm", 45.0, 3),
        ]
        rec = recommend(skills)
        assert rec.recommended_exercise == "long_tone"
        assert rec.focus_areas[0] == "stability"


class TestIntermediateLevel:
    def test_all_skills_60_to_80(self):
        skills = [
            SkillSnapshot("pitch", 72.0, 10),
            SkillSnapshot("stability", 65.0, 8),
            SkillSnapshot("rhythm", 78.0, 12),
        ]
        rec = recommend(skills)
        assert rec.difficulty == "intermediate"
        assert "stability" in rec.focus_areas

    def test_ties_broken_by_exercise_count(self):
        skills = [
            SkillSnapshot("pitch", 70.0, 10),
            SkillSnapshot("stability", 70.0, 5),  # same score, less practiced
            SkillSnapshot("rhythm", 75.0, 8),
        ]
        rec = recommend(skills)
        assert rec.focus_areas[0] == "stability"


class TestAdvancedLevel:
    def test_all_skills_above_80(self):
        skills = [
            SkillSnapshot("pitch", 90.0, 20),
            SkillSnapshot("stability", 85.0, 18),
            SkillSnapshot("rhythm", 88.0, 22),
        ]
        rec = recommend(skills)
        assert rec.recommended_exercise == "melody"
        assert rec.difficulty == "advanced"
        assert "Challenge" in rec.message

    def test_skill_summary_included(self):
        skills = [
            SkillSnapshot("pitch", 92.0, 15),
            SkillSnapshot("stability", 88.0, 12),
        ]
        rec = recommend(skills)
        assert rec.skill_summary["pitch"] == 92.0
        assert rec.skill_summary["stability"] == 88.0


class TestRecommendationAPI:
    """Test the /api/progress/{username}/recommend endpoint."""

    def test_recommend_endpoint(self):
        import os
        os.environ["DATABASE_URL"] = "sqlite:///./test_progression.db"

        from backend.models.database import create_tables
        from backend.main import app
        from fastapi.testclient import TestClient

        create_tables()
        client = TestClient(app)

        # Create user with a session and result
        start_resp = client.post("/api/session/start", json={
            "username": "progression_user",
            "instrument": "erhu",
        })
        session_id = start_resp.json()["session_id"]

        client.post("/api/session/result", json={
            "session_id": session_id,
            "result": {
                "exercise_type": "long_tone",
                "duration_s": 10.0,
                "overall_score": 70.0,
                "pitch_score": 75.0,
                "stability_score": 50.0,
                "rhythm_score": 65.0,
            },
        })

        resp = client.get("/api/progress/progression_user/recommend")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended_exercise" in data
        assert "focus_areas" in data
        assert "difficulty" in data
        assert "message" in data
        assert data["recommended_exercise"] == "long_tone"

    def test_recommend_user_not_found(self):
        import os
        os.environ["DATABASE_URL"] = "sqlite:///./test_progression.db"

        from backend.models.database import create_tables
        from backend.main import app
        from fastapi.testclient import TestClient

        create_tables()
        client = TestClient(app)

        resp = client.get("/api/progress/nonexistent_user_xyz/recommend")
        assert resp.status_code == 404
