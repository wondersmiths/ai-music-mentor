"""
Pydantic schemas for auth endpoints.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: Optional[str] = Field(None, max_length=200)
    instrument: str = Field("erhu", max_length=50)
    role: str = Field("student", pattern="^(student|teacher)$")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=4)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int


class UserInfoResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str]
    role: str
    instrument: str
