"""
Structured logging configuration.

JSON format in production (machine-parseable for Railway logs).
Human-readable format in development.
"""

from __future__ import annotations

import logging
import sys

from backend.config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    if settings.ENVIRONMENT == "development":
        fmt = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
        datefmt = "%H:%M:%S"
    else:
        # Structured format for production log aggregation
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","msg":"%(message)s"}'
        )
        datefmt = "%Y-%m-%dT%H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
