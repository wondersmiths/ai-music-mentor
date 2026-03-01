"""
API2: Session storage endpoints.

POST /api/session/start — begin a training session
POST /api/session/result — save an exercise result
POST /api/session/end — end a training session
GET  /api/progress/{username} — get skill progress
GET  /api/progress/{username}/recommend — get next exercise recommendation
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_optional_user
from backend.models.database import get_db
from backend.models.tables import (
    ExerciseResult,
    PracticeStreak,
    SkillProgress,
    TrainingSession,
    User,
)
from backend.schemas.analysis import ErrorResponse
from ai.progression.engine import SkillSnapshot, recommend
from backend.schemas.session import (
    EndSessionRequest,
    EndSessionResponse,
    ExerciseResultResponse,
    ProgressResponse,
    RecommendationResponse,
    SaveResultRequest,
    SessionHistoryResponse,
    SessionHistoryItem,
    SkillProgressResponse,
    StartSessionRequest,
    StartSessionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["session"])


def _get_or_create_user(db: Session, username: str, instrument: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, instrument=instrument)
        db.add(user)
        db.flush()
    return user


@router.post(
    "/session/start",
    response_model=StartSessionResponse,
    responses={400: {"model": ErrorResponse}},
)
def start_session(req: StartSessionRequest, db: Session = Depends(get_db)):
    """Start a new training session."""
    try:
        user = _get_or_create_user(db, req.username, req.instrument)
        session = TrainingSession(
            user_id=user.id,
            session_id=uuid.uuid4().hex[:16],
            instrument=req.instrument,
            started_at=datetime.utcnow(),
        )
        db.add(session)
        db.commit()

        return StartSessionResponse(session_id=session.session_id, user_id=user.id)
    except Exception:
        db.rollback()
        logger.exception("Failed to start session")
        raise HTTPException(status_code=500, detail="Failed to start session")


@router.post(
    "/session/result",
    responses={404: {"model": ErrorResponse}},
)
def save_result(req: SaveResultRequest, db: Session = Depends(get_db)):
    """Save an exercise result to a training session."""
    session = (
        db.query(TrainingSession)
        .filter(TrainingSession.session_id == req.session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = ExerciseResult(
            session_id=session.id,
            exercise_type=req.result.exercise_type,
            instrument=session.instrument,
            duration_s=req.result.duration_s,
            overall_score=req.result.overall_score,
            pitch_score=req.result.pitch_score,
            stability_score=req.result.stability_score,
            slide_score=req.result.slide_score,
            rhythm_score=req.result.rhythm_score,
            target_frequency=req.result.target_frequency,
            bpm=req.result.bpm,
            feedback=req.result.feedback,
            recommended_next=req.result.recommended_next,
        )
        db.add(result)
        session.exercise_count = (session.exercise_count or 0) + 1
        db.commit()

        # Update skill progress
        _update_skill_progress(db, session.user_id, session.instrument, req.result)

        return {"status": "saved", "exercise_id": result.id}
    except Exception:
        db.rollback()
        logger.exception("Failed to save result")
        raise HTTPException(status_code=500, detail="Failed to save result")


@router.post(
    "/session/end",
    response_model=EndSessionResponse,
    responses={404: {"model": ErrorResponse}},
)
def end_session(req: EndSessionRequest, db: Session = Depends(get_db)):
    """End a training session."""
    session = (
        db.query(TrainingSession)
        .filter(TrainingSession.session_id == req.session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        session.ended_at = datetime.utcnow()
        if session.started_at:
            session.duration_s = (session.ended_at - session.started_at).total_seconds()

        # Compute average score from exercise results
        results = db.query(ExerciseResult).filter(ExerciseResult.session_id == session.id).all()
        if results:
            session.overall_score = sum(r.overall_score for r in results) / len(results)

        # Update practice streak
        _update_streak(db, session.user_id)

        db.commit()

        return EndSessionResponse(
            session_id=session.session_id,
            duration_s=session.duration_s or 0,
            exercise_count=session.exercise_count or 0,
            overall_score=session.overall_score,
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to end session")
        raise HTTPException(status_code=500, detail="Failed to end session")


@router.get(
    "/progress/{username}",
    response_model=ProgressResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_progress(username: str, db: Session = Depends(get_db)):
    """Get skill progress for a user."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total_sessions = (
        db.query(TrainingSession).filter(TrainingSession.user_id == user.id).count()
    )

    skills = db.query(SkillProgress).filter(SkillProgress.user_id == user.id).all()

    return ProgressResponse(
        username=user.username,
        instrument=user.instrument,
        total_sessions=total_sessions,
        skills=[
            SkillProgressResponse(
                skill_area=s.skill_area,
                score=s.score,
                exercise_count=s.exercise_count,
            )
            for s in skills
        ],
    )


@router.get(
    "/progress/{username}/recommend",
    response_model=RecommendationResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_recommendation(username: str, db: Session = Depends(get_db)):
    """Get next exercise recommendation based on skill progress."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total_sessions = (
        db.query(TrainingSession).filter(TrainingSession.user_id == user.id).count()
    )

    skills = db.query(SkillProgress).filter(SkillProgress.user_id == user.id).all()
    snapshots = [
        SkillSnapshot(
            skill_area=s.skill_area,
            score=s.score,
            exercise_count=s.exercise_count,
        )
        for s in skills
    ]

    rec = recommend(snapshots, total_sessions)
    return RecommendationResponse(
        recommended_exercise=rec.recommended_exercise,
        focus_areas=rec.focus_areas,
        difficulty=rec.difficulty,
        message=rec.message,
        skill_summary=rec.skill_summary,
    )


@router.get(
    "/sessions/{username}/history",
    response_model=SessionHistoryResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_session_history(username: str, limit: int = 20, db: Session = Depends(get_db)):
    """Get recent session history with exercise results."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = (
        db.query(TrainingSession)
        .filter(TrainingSession.user_id == user.id)
        .order_by(TrainingSession.started_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for s in sessions:
        results = db.query(ExerciseResult).filter(ExerciseResult.session_id == s.id).all()
        items.append(SessionHistoryItem(
            session_id=s.session_id,
            instrument=s.instrument,
            started_at=s.started_at.isoformat() if s.started_at else "",
            duration_s=s.duration_s or 0,
            exercise_count=s.exercise_count or 0,
            overall_score=s.overall_score,
            exercises=[
                ExerciseResultResponse(
                    exercise_type=r.exercise_type,
                    overall_score=r.overall_score,
                    pitch_score=r.pitch_score,
                    stability_score=r.stability_score,
                    slide_score=r.slide_score,
                    rhythm_score=r.rhythm_score,
                    duration_s=r.duration_s,
                )
                for r in results
            ],
        ))

    return SessionHistoryResponse(username=user.username, sessions=items)


def _update_streak(db: Session, user_id: int):
    """Update practice streak after a session ends."""
    today = date.today()
    streak = db.query(PracticeStreak).filter(PracticeStreak.user_id == user_id).first()

    if not streak:
        streak = PracticeStreak(
            user_id=user_id,
            current_streak=1,
            longest_streak=1,
            last_practice_date=today,
        )
        db.add(streak)
        return

    if streak.last_practice_date == today:
        return  # Already practiced today

    yesterday = today - timedelta(days=1)
    if streak.last_practice_date == yesterday:
        streak.current_streak += 1
    else:
        streak.current_streak = 1

    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak

    streak.last_practice_date = today


def _update_skill_progress(
    db: Session,
    user_id: int,
    instrument: str,
    result,
):
    """Update rolling skill progress from an exercise result."""
    score_map = {
        "pitch": result.pitch_score,
        "stability": result.stability_score,
        "slide": result.slide_score,
        "rhythm": result.rhythm_score,
    }

    for area, score in score_map.items():
        if score is None:
            continue

        progress = (
            db.query(SkillProgress)
            .filter(
                SkillProgress.user_id == user_id,
                SkillProgress.instrument == instrument,
                SkillProgress.skill_area == area,
            )
            .first()
        )

        if progress:
            # Exponential moving average of scores
            alpha = 0.3
            progress.score = round(alpha * score + (1 - alpha) * progress.score, 2)
            progress.exercise_count += 1
        else:
            progress = SkillProgress(
                user_id=user_id,
                instrument=instrument,
                skill_area=area,
                score=round(score, 2),
                exercise_count=1,
            )
            db.add(progress)

    db.commit()
