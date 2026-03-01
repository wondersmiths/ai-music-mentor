"""
Teacher/student workflow endpoints.

POST /api/assignments — teacher creates an assignment
GET  /api/assignments — list assignments (teacher sees given, student sees received)
GET  /api/students/{student_id}/progress — teacher views student progress
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.models.database import get_db
from backend.models.tables import Assignment, SkillProgress, TrainingSession, User
from backend.schemas.session import ProgressResponse, SkillProgressResponse
from backend.schemas.teacher import AssignmentResponse, CreateAssignmentRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher"])


@router.post("/assignments", response_model=AssignmentResponse)
def create_assignment(
    req: CreateAssignmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Teacher creates an assignment for a student."""
    if (user.role or "student") != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can create assignments")

    student = db.query(User).filter(User.username == req.student_username).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    try:
        due = date.fromisoformat(req.due_date) if req.due_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid due_date format (use YYYY-MM-DD)")

    try:
        assignment = Assignment(
            teacher_id=user.id,
            student_id=student.id,
            score_id=req.score_id,
            title=req.title,
            notes=req.notes,
            due_date=due,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        return AssignmentResponse(
            id=assignment.id,
            teacher_id=assignment.teacher_id,
            student_id=assignment.student_id,
            score_id=assignment.score_id,
            title=assignment.title,
            notes=assignment.notes,
            due_date=str(assignment.due_date) if assignment.due_date else None,
            status=assignment.status or "pending",
            created_at=str(assignment.created_at),
            student_username=student.username,
            teacher_username=user.username,
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to create assignment")
        raise HTTPException(status_code=500, detail="Failed to create assignment")


@router.get("/assignments", response_model=List[AssignmentResponse])
def list_assignments(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List assignments. Teachers see given, students see received."""
    if (user.role or "student") == "teacher":
        assignments = (
            db.query(Assignment)
            .filter(Assignment.teacher_id == user.id)
            .order_by(Assignment.created_at.desc())
            .all()
        )
    else:
        assignments = (
            db.query(Assignment)
            .filter(Assignment.student_id == user.id)
            .order_by(Assignment.created_at.desc())
            .all()
        )

    results = []
    for a in assignments:
        student = db.query(User).filter(User.id == a.student_id).first()
        teacher = db.query(User).filter(User.id == a.teacher_id).first()
        results.append(AssignmentResponse(
            id=a.id,
            teacher_id=a.teacher_id,
            student_id=a.student_id,
            score_id=a.score_id,
            title=a.title,
            notes=a.notes,
            due_date=str(a.due_date) if a.due_date else None,
            status=a.status or "pending",
            created_at=str(a.created_at),
            student_username=student.username if student else None,
            teacher_username=teacher.username if teacher else None,
        ))

    return results


@router.get("/students/{student_id}/progress", response_model=ProgressResponse)
def get_student_progress(
    student_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Teacher views a student's progress."""
    if (user.role or "student") != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can view student progress")

    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    total_sessions = (
        db.query(TrainingSession).filter(TrainingSession.user_id == student.id).count()
    )
    skills = db.query(SkillProgress).filter(SkillProgress.user_id == student.id).all()

    return ProgressResponse(
        username=student.username,
        instrument=student.instrument,
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
