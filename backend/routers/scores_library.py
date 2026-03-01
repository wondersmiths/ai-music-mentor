"""
Score library CRUD endpoints.

GET  /api/scores — list built-in + user's scores
POST /api/scores — save a user score (requires auth)
DELETE /api/scores/{id} — delete a user score (requires auth, can't delete built-in)
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user, get_optional_user
from backend.models.database import get_db
from backend.models.tables import SavedScore, User
from backend.schemas.scores_library import SavedScoreResponse, SaveScoreRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["scores"])


@router.get("/scores", response_model=List[SavedScoreResponse])
def list_scores(
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """List built-in scores + current user's saved scores."""
    query = db.query(SavedScore).filter(SavedScore.is_builtin == True)  # noqa: E712

    if user:
        # Also include user's own scores
        query = db.query(SavedScore).filter(
            (SavedScore.is_builtin == True) | (SavedScore.user_id == user.id)  # noqa: E712
        )

    scores = query.order_by(SavedScore.is_builtin.desc(), SavedScore.title).all()
    return [
        SavedScoreResponse(
            id=s.id,
            title=s.title,
            jianpu_notation=s.jianpu_notation,
            key_signature=s.key_signature,
            instrument=s.instrument,
            is_builtin=s.is_builtin,
            user_id=s.user_id,
        )
        for s in scores
    ]


@router.post("/scores", response_model=SavedScoreResponse)
def save_score(
    req: SaveScoreRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a user score to the library."""
    try:
        score = SavedScore(
            user_id=user.id,
            title=req.title,
            jianpu_notation=req.jianpu_notation,
            key_signature=req.key_signature,
            instrument=req.instrument,
            is_builtin=False,
        )
        db.add(score)
        db.commit()
        db.refresh(score)

        return SavedScoreResponse(
            id=score.id,
            title=score.title,
            jianpu_notation=score.jianpu_notation,
            key_signature=score.key_signature,
            instrument=score.instrument,
            is_builtin=score.is_builtin,
            user_id=score.user_id,
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to save score")
        raise HTTPException(status_code=500, detail="Failed to save score")


@router.delete("/scores/{score_id}")
def delete_score(
    score_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user's saved score. Cannot delete built-in scores."""
    score = db.query(SavedScore).filter(SavedScore.id == score_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")

    if score.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in scores")

    if score.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your score")

    try:
        db.delete(score)
        db.commit()
        return {"status": "deleted"}
    except Exception:
        db.rollback()
        logger.exception("Failed to delete score")
        raise HTTPException(status_code=500, detail="Failed to delete score")
