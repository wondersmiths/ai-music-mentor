"""
Auth endpoints: register, login, me.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import (
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)
from backend.models.database import get_db
from backend.models.tables import User
from backend.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInfoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user or upgrade an existing auto-created user."""
    existing = db.query(User).filter(User.username == req.username).first()

    if existing and existing.password_hash:
        raise HTTPException(status_code=409, detail="Username already registered")

    try:
        if existing:
            # Upgrade existing auto-created user (no password yet)
            existing.password_hash = hash_password(req.password)
            existing.display_name = req.display_name or existing.display_name
            existing.role = req.role
            existing.instrument = req.instrument
            db.commit()
            user = existing
        else:
            user = User(
                username=req.username,
                display_name=req.display_name,
                password_hash=hash_password(req.password),
                role=req.role,
                instrument=req.instrument,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_token(user.id, user.username)
        return TokenResponse(
            access_token=token,
            username=user.username,
            user_id=user.id,
        )
    except Exception:
        db.rollback()
        logger.exception("Registration failed")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login with username and password."""
    user = db.query(User).filter(User.username == req.username).first()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        username=user.username,
        user_id=user.id,
    )


@router.get("/me", response_model=UserInfoResponse)
def get_me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return UserInfoResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role or "student",
        instrument=user.instrument,
    )
