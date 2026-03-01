"""
Streak and weekly goal endpoints.

GET  /api/streaks/{username} — streak info
POST /api/goals — set/update weekly goal
GET  /api/goals/{username} — current week goal + progress
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import PracticeStreak, User, WeeklyGoal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["streaks"])


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_practice_date: Optional[str] = None


class WeeklyGoalRequest(BaseModel):
    target_sessions: int = Field(..., ge=1, le=30)
    target_minutes: int = Field(..., ge=10, le=600)


class WeeklyGoalResponse(BaseModel):
    target_sessions: int
    target_minutes: int
    completed_sessions: int
    completed_minutes: float
    week_start: str


@router.get("/streaks/{username}", response_model=StreakResponse)
def get_streak(username: str, db: Session = Depends(get_db)):
    """Get practice streak info for a user."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    streak = db.query(PracticeStreak).filter(PracticeStreak.user_id == user.id).first()
    if not streak:
        return StreakResponse(current_streak=0, longest_streak=0, last_practice_date=None)

    return StreakResponse(
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_practice_date=str(streak.last_practice_date) if streak.last_practice_date else None,
    )


def _current_week_start() -> date:
    """Monday of the current week."""
    today = date.today()
    return today - timedelta(days=today.weekday())


@router.post("/goals", response_model=WeeklyGoalResponse)
def set_weekly_goal(
    req: WeeklyGoalRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or update weekly practice goal."""
    week_start = _current_week_start()

    goal = (
        db.query(WeeklyGoal)
        .filter(WeeklyGoal.user_id == user.id, WeeklyGoal.week_start == week_start)
        .first()
    )

    try:
        if goal:
            goal.target_sessions = req.target_sessions
            goal.target_minutes = req.target_minutes
        else:
            goal = WeeklyGoal(
                user_id=user.id,
                target_sessions=req.target_sessions,
                target_minutes=req.target_minutes,
                week_start=week_start,
            )
            db.add(goal)

        db.commit()

        return WeeklyGoalResponse(
            target_sessions=goal.target_sessions,
            target_minutes=goal.target_minutes,
            completed_sessions=goal.completed_sessions,
            completed_minutes=goal.completed_minutes,
            week_start=str(goal.week_start),
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to set goal")
        raise HTTPException(status_code=500, detail="Failed to set goal")


@router.get("/goals/{username}", response_model=WeeklyGoalResponse)
def get_weekly_goal(username: str, db: Session = Depends(get_db)):
    """Get current week's goal + progress."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    week_start = _current_week_start()
    goal = (
        db.query(WeeklyGoal)
        .filter(WeeklyGoal.user_id == user.id, WeeklyGoal.week_start == week_start)
        .first()
    )

    if not goal:
        raise HTTPException(status_code=404, detail="No goal set for this week")

    return WeeklyGoalResponse(
        target_sessions=goal.target_sessions,
        target_minutes=goal.target_minutes,
        completed_sessions=goal.completed_sessions,
        completed_minutes=goal.completed_minutes,
        week_start=str(goal.week_start),
    )
