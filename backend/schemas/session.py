"""
Pydantic schemas for API2: Session storage endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    instrument: str = Field("erhu", max_length=50)


class StartSessionResponse(BaseModel):
    session_id: str
    user_id: int


class EndSessionRequest(BaseModel):
    session_id: str


class ExerciseResultInput(BaseModel):
    exercise_type: str
    duration_s: float = Field(..., gt=0)
    overall_score: float = Field(..., ge=0, le=100)
    pitch_score: Optional[float] = None
    stability_score: Optional[float] = None
    slide_score: Optional[float] = None
    rhythm_score: Optional[float] = None
    target_frequency: Optional[float] = None
    bpm: Optional[float] = None
    feedback: Optional[str] = None
    recommended_next: Optional[str] = None


class SaveResultRequest(BaseModel):
    session_id: str
    result: ExerciseResultInput


class EndSessionResponse(BaseModel):
    session_id: str
    duration_s: float
    exercise_count: int
    overall_score: Optional[float]


class SkillProgressResponse(BaseModel):
    skill_area: str
    score: float
    exercise_count: int


class ProgressResponse(BaseModel):
    username: str
    instrument: str
    total_sessions: int
    skills: List[SkillProgressResponse]


class RecommendationResponse(BaseModel):
    recommended_exercise: str
    focus_areas: List[str]
    difficulty: str
    message: str
    skill_summary: dict


class ExerciseResultResponse(BaseModel):
    exercise_type: str
    overall_score: float
    pitch_score: Optional[float] = None
    stability_score: Optional[float] = None
    slide_score: Optional[float] = None
    rhythm_score: Optional[float] = None
    duration_s: float


class SessionHistoryItem(BaseModel):
    session_id: str
    instrument: str
    started_at: str
    duration_s: float
    exercise_count: int
    overall_score: Optional[float] = None
    exercises: List[ExerciseResultResponse] = []


class SessionHistoryResponse(BaseModel):
    username: str
    sessions: List[SessionHistoryItem]
