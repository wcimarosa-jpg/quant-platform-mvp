"""Authentication routes — login, token validation, current user.

POST /api/v1/auth/login  — email + password → JWT token
GET  /api/v1/auth/me      — return current user from token
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from packages.shared.auth import authenticate, create_token, decode_token
from packages.shared.db.engine import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: str
    email: str
    role: str
    display_name: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    role: str
    display_name: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate with email + password, receive a JWT."""
    user = authenticate(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_token(user.id, user.email, user.role)
    return LoginResponse(
        token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
    )
