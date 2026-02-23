"""
POST /api/score/parse — accepts a music score image/PDF and returns structured JSON.
POST /api/score/parse-multi — accepts multiple images as pages of one score.
"""

from __future__ import annotations

import logging
from typing import Annotated, List

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import settings
from backend.schemas.score import ScoreResponse
from backend.schemas.analysis import ErrorResponse
from backend.services.score import UnsupportedFileType, parse_score, parse_score_multi

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["score"])

MAX_MULTI_FILES = 20
MAX_MULTI_TOTAL_BYTES = settings.MAX_UPLOAD_BYTES * 5  # 5x single-file limit


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


@router.post(
    "/score/parse-multi",
    response_model=ScoreResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
)
async def parse_multi(
    files: Annotated[List[UploadFile], File(description="Score page images")],
):
    """
    Upload multiple score page images and receive a single structured JSON
    with sequentially numbered measures across all pages.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    if len(files) > MAX_MULTI_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files ({len(files)}). Maximum is {MAX_MULTI_FILES}.",
        )

    file_tuples: list[tuple[bytes, str, str]] = []
    total_size = 0

    for f in files:
        data = await f.read()
        if len(data) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File '{f.filename}' is empty",
            )
        total_size += len(data)
        if total_size > MAX_MULTI_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload size ({total_size} bytes) exceeds maximum "
                f"({MAX_MULTI_TOTAL_BYTES} bytes).",
            )
        file_tuples.append((data, f.filename or "upload.png", f.content_type or ""))

    try:
        return parse_score_multi(file_tuples)
    except UnsupportedFileType as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception:
        logger.exception("Multi-page score parsing failed")
        raise HTTPException(status_code=500, detail="Score recognition failed")
