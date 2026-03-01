"""
Auth endpoints: register, login, me.

Includes per-account lockout and per-IP sliding-window rate limiting.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
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

# ── Per-IP sliding-window rate limiter ───────────────────────

MAX_LOGIN_ATTEMPTS = 10
MAX_REGISTER_ATTEMPTS = 5
RATE_WINDOW_S = 60

# key = (ip, endpoint), value = list of timestamps
_ip_timestamps: dict[str, list[float]] = defaultdict(list)

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def _check_rate_limit(ip: str, endpoint: str, max_attempts: int) -> None:
    """Raise 429 if IP exceeds sliding-window rate limit."""
    key = f"{ip}:{endpoint}"
    now = time.monotonic()
    window_start = now - RATE_WINDOW_S

    # Prune old entries
    timestamps = _ip_timestamps[key]
    _ip_timestamps[key] = [t for t in timestamps if t > window_start]

    if len(_ip_timestamps[key]) >= max_attempts:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(RATE_WINDOW_S)},
        )

    _ip_timestamps[key].append(now)


def _client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new user or upgrade an existing auto-created user."""
    _check_rate_limit(_client_ip(request), "register", MAX_REGISTER_ATTEMPTS)

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
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Login with username and password."""
    _check_rate_limit(_client_ip(request), "login", MAX_LOGIN_ATTEMPTS)

    user = db.query(User).filter(User.username == req.username).first()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check account lockout
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = (user.locked_until - datetime.utcnow()).total_seconds()
        minutes = math.ceil(remaining / 60)
        raise HTTPException(
            status_code=429,
            detail=f"Account temporarily locked. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
        )

    if not verify_password(req.password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
            user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.",
            )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Successful login — reset counters
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

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
