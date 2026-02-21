"""
POST /api/analyze — accepts a WAV audio chunk and returns pitch/onset/tempo analysis.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import settings
from backend.dsp.audio import AudioValidationError
from backend.schemas.analysis import AnalysisResponse, ErrorResponse
from backend.services.analysis import analyze_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def analyze(file: UploadFile = File(..., description="WAV audio chunk (≤15s)")):
    """
    Analyze an uploaded WAV audio chunk.

    Returns detected pitches, onsets, and tempo estimate.
    """
    data = await file.read()

    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data)} bytes). "
            f"Maximum is {settings.MAX_UPLOAD_BYTES} bytes.",
        )

    content_type = file.content_type or ""
    if "wav" not in content_type and not content_type.startswith("audio/"):
        raise HTTPException(
            status_code=415,
            detail=f"Expected audio/wav, got '{content_type}'",
        )

    try:
        return analyze_audio(data)
    except AudioValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail="Audio analysis failed")
