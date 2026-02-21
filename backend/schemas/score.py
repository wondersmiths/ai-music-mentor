"""
Pydantic schemas for score parsing endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreNote(BaseModel):
    pitch: str
    duration: str
    beat: float


class ScoreMeasure(BaseModel):
    number: int
    time_signature: str
    notes: list[ScoreNote]


class ScoreResponse(BaseModel):
    title: str
    confidence: float = Field(..., ge=0, le=1)
    is_mock: bool
    measures: list[ScoreMeasure]
