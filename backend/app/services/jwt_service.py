"""JWT helpers for session tokens and short-lived OAuth state tokens.

Why two token types:
- Session token: lives in an HttpOnly cookie for `jwt_expiry_days`, identifies the user.
- State token: lives for ~10 minutes, signed payload used as the OAuth `state` param
  to prevent CSRF on the callback without needing server-side state storage.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import settings


def create_session_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "session",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.jwt_expiry_days)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict[str, Any] | None:
    """Returns the payload if valid, None otherwise. Never raises."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != "session":
        return None
    return payload


def create_state_token(provider: str) -> str:
    """Short-lived signed token used as the OAuth `state` query param."""
    now = datetime.now(timezone.utc)
    payload = {
        "provider": provider,
        "type": "oauth_state",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_state_token(token: str, expected_provider: str) -> bool:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return False
    return (
        payload.get("type") == "oauth_state"
        and payload.get("provider") == expected_provider
    )
