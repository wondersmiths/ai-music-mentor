"""
Pydantic schemas for score parsing endpoints.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ScoreNote(BaseModel):
    pitch: str
    duration: str
    beat: float
    jianpu: Optional[str] = None


class ScoreMeasure(BaseModel):
    number: int
    time_signature: str
    notes: List[ScoreNote]


class ScoreResponse(BaseModel):
    title: str
    confidence: float = Field(..., ge=0, le=1)
    is_mock: bool
    measures: List[ScoreMeasure]
    notation_type: str = "western"
    key_signature: Optional[str] = None
    page_count: int = 1
