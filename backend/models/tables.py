"""
DB1: Database schema for AI Music Mentor.

Supports multi-instrument future expansion. Tables:
- users: player accounts
- training_sessions: practice session metadata
- exercise_results: per-exercise scores and details
- skill_progress: skill tracking over time
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from backend.models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=True)
    instrument = Column(String(50), nullable=False, default="erhu")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    sessions = relationship("TrainingSession", back_populates="user")
    progress = relationship("SkillProgress", back_populates="user")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    instrument = Column(String(50), nullable=False, default="erhu")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_s = Column(Float, nullable=True)
    exercise_count = Column(Integer, default=0)
    overall_score = Column(Float, nullable=True)

    user = relationship("User", back_populates="sessions")
    results = relationship("ExerciseResult", back_populates="session")


class ExerciseResult(Base):
    __tablename__ = "exercise_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=False, index=True)
    exercise_type = Column(String(50), nullable=False)  # long_tone, scale, melody
    instrument = Column(String(50), nullable=False, default="erhu")
    duration_s = Column(Float, nullable=False)
    overall_score = Column(Float, nullable=False)
    pitch_score = Column(Float, nullable=True)
    stability_score = Column(Float, nullable=True)
    slide_score = Column(Float, nullable=True)
    rhythm_score = Column(Float, nullable=True)
    target_frequency = Column(Float, nullable=True)
    bpm = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    recommended_next = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    session = relationship("TrainingSession", back_populates="results")


class SkillProgress(Base):
    __tablename__ = "skill_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    instrument = Column(String(50), nullable=False, default="erhu")
    skill_area = Column(String(50), nullable=False)  # pitch, stability, slide, rhythm
    score = Column(Float, nullable=False)
    exercise_count = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="progress")
