import hashlib
import hmac
import logging
import secrets
import time
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.auth.service import create_token, create_user, get_user_by_email

router = APIRouter()
logger = logging.getLogger(__name__)

_FRONTEND_LOGIN = "https://mate.molmont.com.ar/login"


def _make_state() -> str:
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    msg = f"{nonce}:{ts}"
    sig = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}:{sig}"


def _verify_state(state: str) -> bool:
    try:
        nonce, ts, sig = state.rsplit(":", 2)
        msg = f"{nonce}:{ts}"
        expected = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        if time.time() - int(ts) > 300:
            return False
        return True
    except Exception:
        return False


async def _find_or_create_oauth_user(db: AsyncSession, email: str, name: str):
    """
    Allow login only if:
    - User already exists in DB, OR
    - Email matches OAUTH_ADMIN_EMAIL (first-time admin bootstrap)
    Returns user or None if access denied.
    """
    user = await get_user_by_email(db, email)
    if user:
        return user

    admin_email = settings.OAUTH_ADMIN_EMAIL.strip().lower()
    if email.strip().lower() == admin_email:
        logger.info(f"OAuth: bootstrapping admin user {email}")
        user = await create_user(db, email, name, f"OAUTH_{uuid.uuid4().hex}_Aa1!")
        # Mark as admin
        user.is_admin = True
        await db.commit()
        await db.refresh(user)
        return user

    logger.warning(f"OAuth: access denied for unregistered email {email}")
    return None


# ── Google ────────────────────────────────────────────────────────────────────
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_GOOGLE_REDIRECT_URI = "https://mate.molmont.com.ar/api/v1/auth/google/callback"


@router.get("/auth/google")
async def google_login():
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": _make_state(),
        "access_type": "offline",
        "prompt": "select_account",
    })
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{params}")


@router.get("/auth/google/callback")
async def google_callback(
    code: str = None,
    state: str = None,
    error: str = None,
    db: AsyncSession = Depends(get_db),
):
    if error or not code:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=google_denied")
    if not state or not _verify_state(state):
        logger.warning("Google OAuth: state verification failed")
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=state_mismatch")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": _GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            logger.error(f"Google token exchange failed: {token_resp.text}")
            return RedirectResponse(f"{_FRONTEND_LOGIN}?error=token_exchange")

        access_token = token_resp.json().get("access_token")
        userinfo_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(f"{_FRONTEND_LOGIN}?error=userinfo")

        userinfo = userinfo_resp.json()

    email = userinfo.get("email")
    if not email:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=no_email")

    name = userinfo.get("name") or email.split("@")[0]
    user = await _find_or_create_oauth_user(db, email, name)
    if not user:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=not_allowed")

    token = create_token(user.id, user.email)
    return RedirectResponse(f"{_FRONTEND_LOGIN}?{urlencode({'token': token, 'name': user.name, 'email': user.email})}")


# ── Microsoft ─────────────────────────────────────────────────────────────────
_MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MS_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"
_MS_REDIRECT_URI = "https://mate.molmont.com.ar/api/v1/auth/microsoft/callback"


@router.get("/auth/microsoft")
async def microsoft_login():
    params = urlencode({
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "redirect_uri": _MS_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile User.Read",
        "state": _make_state(),
        "prompt": "select_account",
    })
    return RedirectResponse(f"{_MS_AUTH_URL}?{params}")


@router.get("/auth/microsoft/url")
async def microsoft_login_url():
    """Returns the Microsoft OAuth URL as JSON so the frontend can redirect client-side."""
    params = urlencode({
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "redirect_uri": _MS_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile User.Read",
        "state": _make_state(),
        "prompt": "select_account",
    })
    return {"url": f"{_MS_AUTH_URL}?{params}"}


@router.get("/auth/microsoft/callback")
async def microsoft_callback(
    code: str = None,
    state: str = None,
    error: str = None,
    db: AsyncSession = Depends(get_db),
):
    if error or not code:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=microsoft_denied")
    if not state or not _verify_state(state):
        logger.warning("Microsoft OAuth: state verification failed")
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=state_mismatch")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(_MS_TOKEN_URL, data={
            "code": code,
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "redirect_uri": _MS_REDIRECT_URI,
            "grant_type": "authorization_code",
            "scope": "openid email profile User.Read",
        })
        if token_resp.status_code != 200:
            logger.error(f"Microsoft token exchange failed: {token_resp.text}")
            return RedirectResponse(f"{_FRONTEND_LOGIN}?error=token_exchange")

        access_token = token_resp.json().get("access_token")
        userinfo_resp = await client.get(
            _MS_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(f"{_FRONTEND_LOGIN}?error=userinfo")

        userinfo = userinfo_resp.json()

    email = userinfo.get("mail") or userinfo.get("userPrincipalName")
    if not email:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=no_email")

    name = userinfo.get("displayName") or email.split("@")[0]
    user = await _find_or_create_oauth_user(db, email, name)
    if not user:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=not_allowed")

    token = create_token(user.id, user.email)
    return RedirectResponse(f"{_FRONTEND_LOGIN}?{urlencode({'token': token, 'name': user.name, 'email': user.email})}")
