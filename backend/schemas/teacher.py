"""
Pydantic schemas for teacher/assignment endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CreateAssignmentRequest(BaseModel):
    student_username: str = Field(..., min_length=1)
    score_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string


class AssignmentResponse(BaseModel):
    id: int
    teacher_id: int
    student_id: int
    score_id: Optional[int] = None
    title: str
    notes: Optional[str] = None
    due_date: Optional[str] = None
    status: str
    created_at: str
    student_username: Optional[str] = None
    teacher_username: Optional[str] = None
