"""
Backend API server for AI Music Mentor.

Exposes POST /api/score/parse for uploading sheet music images/PDFs
and returning structured JSON via the OMR pipeline.
"""

import logging
import os
import sys
import tempfile
import time

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

# Allow imports from the project root so the ai.omr package is reachable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.omr.pipeline import recognize  # noqa: E402

# ── Logging setup ───────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backend")

# ── App ─────────────────────────────────────────────────────

ALLOWED_TYPES = {
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "application/pdf",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

app = FastAPI(
    title="AI Music Mentor — Backend",
    version="0.1.0",
)


# ── Middleware: request logging ─────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info(
        "%s %s → %d (%.0f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# ── Routes ──────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/api/score/parse")
async def parse_score(file: UploadFile = File(...)):
    """
    Accept an uploaded image or PDF of a music score and return
    structured JSON with measures, notes, pitch, and duration.
    """
    # -- Validate content type --
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        logger.warning("Rejected file: unsupported type %s", content_type)
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type}'. "
            f"Accepted: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    # -- Read and validate size --
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data)} bytes). Maximum is {MAX_FILE_SIZE} bytes.",
        )

    filename = file.filename or "upload.png"
    suffix = os.path.splitext(filename)[1] or ".png"
    logger.info("Received file: %s (%d bytes, %s)", filename, len(data), content_type)

    # -- Write to temp file for the OMR pipeline --
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        result = recognize(tmp_path)

        logger.info(
            "Recognition complete: confidence=%.3f, is_mock=%s, measures=%d",
            result.confidence,
            result.is_mock,
            len(result.measures),
        )
        return result.model_dump()

    except HTTPException:
        raise
    except Exception:
        logger.exception("OMR pipeline failed for %s", filename)
        raise HTTPException(status_code=500, detail="Score recognition failed")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Global exception handler ───────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Entrypoint ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)
