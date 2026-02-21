"""
POST /api/practice/start  — begin a new practice session
POST /api/practice/frame  — send an audio chunk for real-time alignment
POST /api/practice/stop   — end session and get analysis + practice plan
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from backend.dsp.audio import AudioValidationError
from backend.schemas.analysis import ErrorResponse
from backend.schemas.practice import (
    FrameResponse,
    StartRequest,
    StartResponse,
    StopRequest,
    StopResponse,
)
from backend.services.practice import (
    process_frame,
    start_session,
    stop_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.post(
    "/start",
    response_model=StartResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def practice_start(req: StartRequest):
    """Begin a new practice session with a score and tempo."""
    if not req.measures:
        raise HTTPException(status_code=400, detail="Score must have at least one measure")

    try:
        return start_session(req)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception:
        logger.exception("Failed to start practice session")
        raise HTTPException(status_code=500, detail="Failed to start practice session")


@router.post(
    "/frame",
    response_model=FrameResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def practice_frame(
    session_id: str = Form(...),
    file: UploadFile = File(..., description="WAV audio chunk (~2s)"),
):
    """Process an audio frame for real-time alignment."""
    data = await file.read()

    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    try:
        result = await run_in_threadpool(process_frame, session_id, data)
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AudioValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Frame processing failed for session %s", session_id)
        raise HTTPException(status_code=500, detail="Frame processing failed")


@router.post(
    "/stop",
    response_model=StopResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def practice_stop(req: StopRequest):
    """Stop a practice session and return analysis + practice plan."""
    try:
        result = await run_in_threadpool(stop_session, req.session_id)
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Failed to stop session %s", req.session_id)
        raise HTTPException(status_code=500, detail="Analysis failed")
