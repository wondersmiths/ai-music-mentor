"""
Seed built-in scores into the database.

Called at startup, idempotent — checks if scores already exist.
"""

from __future__ import annotations

import logging

from backend.models.database import SessionLocal
from backend.models.tables import SavedScore

logger = logging.getLogger(__name__)

BUILTIN_SCORES = [
    {
        "title": "D Major Scale",
        "jianpu_notation": "1 2 3 4 5 6 7 1\u0307",
        "key_signature": "1=D",
        "instrument": None,
    },
    {
        "title": "Pentatonic Scale",
        "jianpu_notation": "1 2 3 5 6 1\u0307",
        "key_signature": "1=D",
        "instrument": None,
    },
    {
        "title": "Twinkle Twinkle",
        "jianpu_notation": "1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 -",
        "key_signature": "1=D",
        "instrument": None,
    },
    {
        "title": "Mo Li Hua (Jasmine Flower)",
        "jianpu_notation": "3 3 5 6 | 1\u0307 6 5 - | 5 3 5 6 | 5 - - -",
        "key_signature": "1=D",
        "instrument": None,
    },
    {
        "title": "Long Tone D5",
        "jianpu_notation": "5 - - - | 5 - - -",
        "key_signature": "1=D",
        "instrument": None,
    },
]


def seed_builtin_scores():
    """Insert built-in scores if they don't already exist."""
    db = SessionLocal()
    try:
        existing = db.query(SavedScore).filter(SavedScore.is_builtin == True).count()  # noqa: E712
        if existing > 0:
            return  # Already seeded

        for s in BUILTIN_SCORES:
            score = SavedScore(
                title=s["title"],
                jianpu_notation=s["jianpu_notation"],
                key_signature=s["key_signature"],
                instrument=s["instrument"],
                is_builtin=True,
                user_id=None,
            )
            db.add(score)

        db.commit()
        logger.info("Seeded %d built-in scores", len(BUILTIN_SCORES))
    except Exception:
        db.rollback()
        logger.exception("Failed to seed built-in scores")
    finally:
        db.close()
