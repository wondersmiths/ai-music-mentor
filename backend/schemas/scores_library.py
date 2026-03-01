"""
Pydantic schemas for the score library endpoints.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SaveScoreRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    jianpu_notation: str = Field(..., min_length=1)
    key_signature: Optional[str] = Field(None, max_length=20)
    instrument: Optional[str] = Field(None, max_length=50)


class SavedScoreResponse(BaseModel):
    id: int
    title: str
    jianpu_notation: str
    key_signature: Optional[str] = None
    instrument: Optional[str] = None
    is_builtin: bool
    user_id: Optional[int] = None
