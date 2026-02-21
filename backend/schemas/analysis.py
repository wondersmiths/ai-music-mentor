"""
Pydantic request/response schemas for the audio analysis endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Responses ────────────────────────────────────────────────

class PitchEvent(BaseModel):
    time: float = Field(..., description="Seconds from chunk start")
    note: str = Field(..., description="Note name, e.g. 'A4'")
    frequency: float = Field(..., ge=0, description="Hz")
    cents_off: int = Field(..., ge=-50, le=50)
    confidence: float = Field(..., ge=0, le=1)


class OnsetEvent(BaseModel):
    time: float = Field(..., description="Seconds from chunk start")
    strength: float = Field(..., ge=0)


class TempoResult(BaseModel):
    bpm: float = Field(..., ge=0)
    confidence: float = Field(..., ge=0, le=1)


class AnalysisResponse(BaseModel):
    pitches: list[PitchEvent]
    onsets: list[OnsetEvent]
    tempo: TempoResult
    duration_s: float = Field(..., description="Audio chunk duration in seconds")


# ── Health / Meta ────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str = ""
    version: str = ""


class ErrorResponse(BaseModel):
    detail: str
