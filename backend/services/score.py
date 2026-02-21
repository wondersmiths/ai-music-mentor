"""
Score parsing service — wraps the OMR pipeline.
"""

from __future__ import annotations

import logging
import os
import tempfile

from ai.omr.pipeline import recognize
from backend.schemas.score import ScoreResponse

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "application/pdf",
}


class UnsupportedFileType(Exception):
    pass


def parse_score(data: bytes, filename: str, content_type: str) -> ScoreResponse:
    """
    Run the OMR pipeline on uploaded file bytes.

    Raises UnsupportedFileType for invalid content types.
    """
    if content_type not in ALLOWED_TYPES:
        raise UnsupportedFileType(
            f"Unsupported file type '{content_type}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_TYPES))}"
        )

    suffix = os.path.splitext(filename)[1] or ".png"
    logger.info("Parsing score: %s (%d bytes, %s)", filename, len(data), content_type)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        result = recognize(tmp_path)

        logger.info(
            "Recognition complete: confidence=%.3f, is_mock=%s, measures=%d",
            result.confidence, result.is_mock, len(result.measures),
        )
        return ScoreResponse(**result.model_dump())

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
