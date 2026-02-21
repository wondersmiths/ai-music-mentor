"""
Pydantic request/response schemas for the practice session endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.analysis import PitchEvent, OnsetEvent
from backend.schemas.score import ScoreMeasure


# ── Start ────────────────────────────────────────────────────

class StartRequest(BaseModel):
    title: str = ""
    measures: list[ScoreMeasure]
    bpm: float = Field(120.0, ge=20, le=400)


class StartResponse(BaseModel):
    session_id: str
    total_notes: int
    total_measures: int


# ── Frame ────────────────────────────────────────────────────

class FrameAlignmentUpdate(BaseModel):
    current_measure: int = Field(..., description="1-based measure number")
    current_beat: float = Field(..., description="Beat within the measure")
    confidence: float = Field(..., ge=0, le=1)
    is_complete: bool


class FrameResponse(BaseModel):
    alignment: FrameAlignmentUpdate
    pitches: list[PitchEvent]
    onsets: list[OnsetEvent]
    elapsed_s: float


# ── Stop ─────────────────────────────────────────────────────

class IssueDetail(BaseModel):
    type: str
    severity: str
    measure: int
    detail: str


class ErhuAnalysis(BaseModel):
    issues: list[IssueDetail]
    accuracy: float = Field(..., ge=0, le=1)
    rhythm_score: float = Field(..., ge=0, le=1)


class DrillDetail(BaseModel):
    measure: int
    priority: str
    issue_summary: str
    suggested_tempo: int
    repetitions: int
    tip: str


class PracticePlanResult(BaseModel):
    summary: str
    accuracy_pct: int
    rhythm_pct: int
    priority_measures: list[int]
    drills: list[DrillDetail]
    warmup: str
    closing: str


class StopRequest(BaseModel):
    session_id: str


class StopResponse(BaseModel):
    erhu_analysis: ErhuAnalysis
    practice_plan: PracticePlanResult
