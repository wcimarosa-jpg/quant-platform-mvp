"""FastAPI auth dependencies — inject current user into route handlers.

Usage in routes:
    from apps.api.auth_deps import get_current_user, CurrentUser

    @router.get("/projects")
    def list_projects(user: CurrentUser):
        ...  # user is a TokenPayload with .sub, .email, .role
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from packages.shared.auth import TokenPayload, decode_token


def _extract_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    return auth[7:]


def get_current_user(token: str = Depends(_extract_token)) -> TokenPayload:
    """Decode and validate the JWT. Returns the token payload."""
    try:
        return decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


# Annotated type alias for route signatures
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
