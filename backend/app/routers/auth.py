"""OAuth login + session endpoints.

Flow:
  1. GET  /api/auth/{provider}/login     -> 302 to Google/GitHub
  2. GET  /api/auth/{provider}/callback  -> exchange code, upsert user,
                                            set HttpOnly session cookie,
                                            302 to APP_URL/
  3. GET  /api/auth/me                   -> current user as JSON
  4. POST /api/auth/logout               -> clear cookie

State (CSRF) is a short-lived signed JWT — no server-side storage needed.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import SESSION_COOKIE, get_current_user
from app.models import User
from app.services import oauth
from app.services.jwt_service import (
    create_session_token,
    create_state_token,
    decode_state_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

SUPPORTED_PROVIDERS = {"google", "github"}


def _cookie_secure() -> bool:
    # Only send the cookie over HTTPS in real environments.
    # Plain http://localhost dev still needs to work.
    return settings.app_url.startswith("https://")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",  # must be lax (not strict) so the cookie is sent
                          # on the cross-site redirect back from Google/GitHub
        max_age=settings.jwt_expiry_days * 24 * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


# ---------------------------------------------------------------------------
# Login: redirect to provider
# ---------------------------------------------------------------------------

@router.get("/{provider}/login")
async def login(provider: str) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")

    # Fail fast in dev if OAuth isn't configured yet.
    client_id = getattr(settings, f"{provider}_client_id", "")
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail=f"{provider} OAuth is not configured (missing client_id)",
        )

    state = create_state_token(provider)
    url = oauth.authorize_url(provider, state)
    return RedirectResponse(url=url, status_code=302)


# ---------------------------------------------------------------------------
# Callback: exchange code, upsert user, issue session cookie
# ---------------------------------------------------------------------------

@router.get("/{provider}/callback")
async def callback(
    provider: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")

    if error:
        # User denied consent or provider rejected the request.
        return RedirectResponse(url=f"{settings.app_url}/?auth_error={error}", status_code=302)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    if not decode_state_token(state, provider):
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    try:
        info = await oauth.exchange_code(provider, code)
    except oauth.OAuthError as e:
        # Log the full upstream error so we can see WHY Google/GitHub rejected
        # the exchange. Without this, the detail vanishes into an HTTP response
        # body the browser drops mid-redirect.
        logger.error("OAuth %s exchange failed: %s", provider, e)
        return RedirectResponse(
            url=f"{settings.app_url}/?auth_error=exchange_failed",
            status_code=302,
        )

    # Upsert user by (oauth_provider, oauth_id)
    result = await db.execute(
        select(User).where(
            User.oauth_provider == info.provider,
            User.oauth_id == info.oauth_id,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=info.email,
            name=info.name,
            avatar_url=info.avatar_url,
            oauth_provider=info.provider,
            oauth_id=info.oauth_id,
            tier="free",
        )
        db.add(user)
    else:
        # Refresh profile fields in case they changed upstream
        user.email = info.email
        user.name = info.name
        user.avatar_url = info.avatar_url
        user.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)

    token = create_session_token(str(user.id), user.email)
    response = RedirectResponse(url=f"{settings.app_url}/", status_code=302)
    _set_session_cookie(response, token)
    return response


# ---------------------------------------------------------------------------
# Current user + logout
# ---------------------------------------------------------------------------

@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "tier": user.tier,
        "oauth_provider": user.oauth_provider,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
