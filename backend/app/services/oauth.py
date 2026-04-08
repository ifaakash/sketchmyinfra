"""OAuth 2.0 Authorization Code flow clients for Google and GitHub.

Each provider exposes two functions:
  - authorize_url(state) -> str    : where to send the user to log in
  - exchange_code(code) -> UserInfo: swap an auth code for normalized user info

We use raw httpx rather than an OAuth library to keep the dependency surface
small and the protocol explicit. The flow is short enough that wrapping it
adds more confusion than it saves.
"""
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings


@dataclass
class OAuthUserInfo:
    provider: str       # "google" | "github"
    oauth_id: str       # provider's stable user id
    email: str
    name: str | None
    avatar_url: str | None


class OAuthError(Exception):
    pass


def _callback_url(provider: str) -> str:
    return f"{settings.app_url}/api/auth/{provider}/callback"


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def google_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": _callback_url("google"),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def google_exchange_code(code: str) -> OAuthUserInfo:
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": _callback_url("google"),
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            raise OAuthError(f"Google token exchange failed: {token_resp.text}")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise OAuthError("Google did not return an access token")

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise OAuthError(f"Google userinfo failed: {userinfo_resp.text}")
        data = userinfo_resp.json()

    if not data.get("sub") or not data.get("email"):
        raise OAuthError("Google userinfo missing required fields")

    return OAuthUserInfo(
        provider="google",
        oauth_id=str(data["sub"]),
        email=data["email"],
        name=data.get("name"),
        avatar_url=data.get("picture"),
    )


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def github_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": _callback_url("github"),
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"


async def github_exchange_code(code: str) -> OAuthUserInfo:
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "redirect_uri": _callback_url("github"),
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            raise OAuthError(f"GitHub token exchange failed: {token_resp.text}")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise OAuthError("GitHub did not return an access token")

        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }

        user_resp = await client.get(GITHUB_USER_URL, headers=auth_headers)
        if user_resp.status_code != 200:
            raise OAuthError(f"GitHub user fetch failed: {user_resp.text}")
        user = user_resp.json()

        # GitHub's /user returns email=null if the user keeps it private.
        # Fall back to /user/emails and pick the primary verified one.
        email = user.get("email")
        if not email:
            emails_resp = await client.get(GITHUB_EMAILS_URL, headers=auth_headers)
            if emails_resp.status_code == 200:
                for entry in emails_resp.json():
                    if entry.get("primary") and entry.get("verified"):
                        email = entry.get("email")
                        break

    if not user.get("id") or not email:
        raise OAuthError("GitHub user missing id or verified email")

    return OAuthUserInfo(
        provider="github",
        oauth_id=str(user["id"]),
        email=email,
        name=user.get("name") or user.get("login"),
        avatar_url=user.get("avatar_url"),
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def authorize_url(provider: str, state: str) -> str:
    if provider == "google":
        return google_authorize_url(state)
    if provider == "github":
        return github_authorize_url(state)
    raise OAuthError(f"Unknown provider: {provider}")


async def exchange_code(provider: str, code: str) -> OAuthUserInfo:
    if provider == "google":
        return await google_exchange_code(code)
    if provider == "github":
        return await github_exchange_code(code)
    raise OAuthError(f"Unknown provider: {provider}")
