"""
Pydantic request/response schemas for the practice evaluation endpoint (API1).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request ─────────────────────────────────────────────────

class PitchFrameInput(BaseModel):
    time: float = Field(..., description="Seconds since recording start")
    frequency: float = Field(..., ge=0, description="Hz")
    confidence: float = Field(..., ge=0, le=1)


class ReferencePoint(BaseModel):
    time: float = Field(..., description="Seconds")
    frequency: float = Field(..., ge=0, description="Hz")


class EvaluateRequest(BaseModel):
    exercise_type: str = Field(..., description="e.g. long_tone, scale, melody")
    frames: List[PitchFrameInput] = Field(..., min_length=1)
    duration: float = Field(..., gt=0, le=60, description="Session duration in seconds")
    target_frequency: Optional[float] = Field(None, gt=0, description="Target Hz for long_tone")
    reference_curve: Optional[List[ReferencePoint]] = Field(
        None, description="Expected pitch curve for scale/melody exercises"
    )
    bpm: Optional[float] = Field(None, gt=0, description="Beats per minute")


# ── Response ────────────────────────────────────────────────

class UnstableSegmentResponse(BaseModel):
    start_time: float
    end_time: float
    mean_deviation_cents: float


class StabilityDetail(BaseModel):
    stability_score: float
    mean_deviation_cents: float
    variance_cents: float
    unstable_ranges: List[UnstableSegmentResponse] = []


class DTWDetail(BaseModel):
    pitch_error_mean: float
    timing_deviation: float
    path_length: int


class SlideSegmentResponse(BaseModel):
    start_time: float
    end_time: float
    start_freq: float
    end_freq: float
    interval_cents: float
    smoothness: float
    overshoot_cents: float
    has_step_artifact: bool


class SlideDetail(BaseModel):
    slide_score: float
    slide_count: int
    segments: List[SlideSegmentResponse] = []


class RhythmDetail(BaseModel):
    rhythm_score: float
    mean_deviation_ms: float
    max_deviation_ms: float
    tempo_drift: float
    onset_count: int
    expected_onset_count: int


class EvaluateResponse(BaseModel):
    overall_score: float = Field(..., ge=0, le=100)
    pitch_score: float = Field(..., ge=0, le=100)
    stability_score: float = Field(..., ge=0, le=100)
    slide_score: float = Field(..., ge=0, le=100)
    rhythm_score: float = Field(..., ge=0, le=100)
    recommended_training_type: str
    textual_feedback: str
    stability_detail: Optional[StabilityDetail] = None
    dtw_detail: Optional[DTWDetail] = None
    slide_detail: Optional[SlideDetail] = None
    rhythm_detail: Optional[RhythmDetail] = None
