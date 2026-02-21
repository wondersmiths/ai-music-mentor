"""
POST /api/score/parse — accepts a music score image/PDF and returns structured JSON.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import settings
from backend.schemas.score import ScoreResponse
from backend.schemas.analysis import ErrorResponse
from backend.services.score import UnsupportedFileType, parse_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["score"])


@router.post(
    "/score/parse",
    response_model=ScoreResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
)
async def parse(file: UploadFile = File(..., description="Score image or PDF")):
    """
    Upload a music score image or PDF and receive structured JSON
    with measures, notes, pitches, and durations.
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

    try:
        return parse_score(
            data=data,
            filename=file.filename or "upload.png",
            content_type=file.content_type or "",
        )
    except UnsupportedFileType as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception:
        logger.exception("Score parsing failed")
        raise HTTPException(status_code=500, detail="Score recognition failed")
