"""FastAPI dependencies for reading the current user from a session cookie.

Two flavors:
  - get_current_user           : required auth, 401 if missing/invalid
  - get_current_user_optional  : returns None if missing/invalid (for endpoints
                                 that behave differently for guests, like
                                 rate-limited generation)
"""
import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.services.jwt_service import decode_session_token

SESSION_COOKIE = "session"


async def get_current_user_optional(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not session:
        return None
    payload = decode_session_token(session)
    if not payload:
        return None
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user
