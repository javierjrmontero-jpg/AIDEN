import secrets
import uuid
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.auth.service import create_token, create_user, get_user_by_email

router = APIRouter()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_REDIRECT_URI = "https://mate.molmont.com.ar/api/v1/auth/google/callback"
_FRONTEND_LOGIN = "https://mate.molmont.com.ar/login"


@router.get("/auth/google")
async def google_login():
    state = secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    })
    response = RedirectResponse(f"{_GOOGLE_AUTH_URL}?{params}")
    response.set_cookie("oauth_state", state, max_age=300, secure=True, httponly=True, samesite="lax")
    return response


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: AsyncSession = Depends(get_db),
):
    if error or not code:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=google_denied")

    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state:
        return RedirectResponse(f"{_FRONTEND_LOGIN}?error=state_mismatch")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": _REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
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

    user = await get_user_by_email(db, email)
    if not user:
        # OAuth users get a random unusable password
        user = await create_user(db, email, name, f"OAUTH_{uuid.uuid4().hex}_Aa1!")

    token = create_token(user.id, user.email)
    params = urlencode({"token": token, "name": user.name, "email": user.email})
    response = RedirectResponse(f"{_FRONTEND_LOGIN}?{params}")
    response.delete_cookie("oauth_state")
    return response
