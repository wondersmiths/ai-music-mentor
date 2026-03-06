"""
POST /api/evaluate — accepts a practice session JSON and returns evaluation scores.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.schemas.analysis import ErrorResponse
from backend.schemas.evaluation import (
    DTWDetail,
    EvaluateRequest,
    EvaluateResponse,
    RhythmDetail,
    SlideDetail,
    SlideSegmentResponse,
    StabilityDetail,
    UnstableSegmentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["evaluation"])


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def evaluate_practice(req: EvaluateRequest):
    """
    Evaluate a recorded practice session.

    Accepts the pitch frames captured by the frontend session recorder (F6),
    runs the evaluation pipeline (DTW alignment, stability analysis, aggregation),
    and returns scores with actionable feedback.
    """
    # Validate duration
    if req.duration > 60:
        raise HTTPException(status_code=400, detail="Session duration exceeds 60 second limit")

    if not req.frames:
        raise HTTPException(status_code=400, detail="No pitch frames provided")

    try:
        from ai.evaluation.aggregator import evaluate

        # Convert request models to tuples for the evaluation pipeline
        played_frames = [
            (f.time, f.frequency, f.confidence)
            for f in req.frames
        ]

        reference_curve = None
        if req.reference_curve:
            reference_curve = [(p.time, p.frequency) for p in req.reference_curve]

        # Debug: log what we're sending to the evaluator
        freqs = [f for _, f, _ in played_frames if f > 0]
        logger.info(
            "Evaluate request: exercise=%s, frames=%d, voiced=%d, "
            "freq_range=%.1f–%.1f Hz, duration=%.2f, "
            "target_freq=%s, ref_curve_len=%s, bpm=%s",
            req.exercise_type,
            len(played_frames),
            len(freqs),
            min(freqs) if freqs else 0,
            max(freqs) if freqs else 0,
            req.duration,
            req.target_frequency,
            len(reference_curve) if reference_curve else None,
            req.bpm,
        )

        result = evaluate(
            played_frames=played_frames,
            exercise_type=req.exercise_type,
            target_frequency=req.target_frequency,
            reference_curve=reference_curve,
            bpm=req.bpm,
        )

        logger.info(
            "Evaluate result: overall=%.1f, pitch=%.1f, stability=%.1f, "
            "slide=%.1f, rhythm=%.1f",
            result.overall_score,
            result.pitch_score,
            result.stability_score,
            result.slide_score,
            result.rhythm_score,
        )

        # Build response
        stability_detail = None
        if result.stability_result:
            sr = result.stability_result
            stability_detail = StabilityDetail(
                stability_score=sr.stability_score,
                mean_deviation_cents=sr.mean_deviation_cents,
                variance_cents=sr.variance_cents,
                unstable_ranges=[
                    UnstableSegmentResponse(
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        mean_deviation_cents=seg.mean_deviation_cents,
                    )
                    for seg in sr.unstable_ranges
                ],
            )

        dtw_detail = None
        if result.dtw_result:
            dr = result.dtw_result
            dtw_detail = DTWDetail(
                pitch_error_mean=dr.pitch_error_mean,
                timing_deviation=dr.timing_deviation,
                path_length=len(dr.alignment_path),
            )

        slide_detail = None
        if result.slide_result:
            sr2 = result.slide_result
            slide_detail = SlideDetail(
                slide_score=sr2.slide_score,
                slide_count=sr2.slide_count,
                segments=[
                    SlideSegmentResponse(
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        start_freq=seg.start_freq,
                        end_freq=seg.end_freq,
                        interval_cents=seg.interval_cents,
                        smoothness=seg.smoothness,
                        overshoot_cents=seg.overshoot_cents,
                        has_step_artifact=seg.has_step_artifact,
                    )
                    for seg in sr2.segments
                ],
            )

        rhythm_detail = None
        if result.rhythm_result:
            rr = result.rhythm_result
            rhythm_detail = RhythmDetail(
                rhythm_score=rr.rhythm_score,
                mean_deviation_ms=rr.mean_deviation_ms,
                max_deviation_ms=rr.max_deviation_ms,
                tempo_drift=rr.tempo_drift,
                onset_count=rr.onset_count,
                expected_onset_count=rr.expected_onset_count,
            )

        return EvaluateResponse(
            overall_score=result.overall_score,
            pitch_score=result.pitch_score,
            stability_score=result.stability_score,
            slide_score=result.slide_score,
            rhythm_score=result.rhythm_score,
            recommended_training_type=result.recommended_training_type,
            textual_feedback=result.textual_feedback,
            stability_detail=stability_detail,
            dtw_detail=dtw_detail,
            slide_detail=slide_detail,
            rhythm_detail=rhythm_detail,
        )

    except Exception:
        logger.exception("Evaluation failed")
        raise HTTPException(status_code=500, detail="Evaluation failed")
