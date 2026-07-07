import hashlib
import hmac
import secrets
import time

import pyotp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.services.auth.service import create_token

router = APIRouter()

_MFA_TOKEN_TTL = 300  # 5 minutes


def _make_mfa_token(user_id: str) -> str:
    ts = str(int(time.time()))
    msg = f"{user_id}:{ts}"
    sig = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}:{sig}"


def _verify_mfa_token(token: str) -> str | None:
    """Returns user_id if valid, None otherwise."""
    try:
        user_id, ts, sig = token.rsplit(":", 2)
        msg = f"{user_id}:{ts}"
        expected = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if time.time() - int(ts) > _MFA_TOKEN_TTL:
            return None
        return user_id
    except Exception:
        return None


@router.get("/auth/mfa/setup")
async def mfa_setup(current_user: User = Depends(get_current_user)):
    """Generate a TOTP secret for the authenticated user (not yet enabled)."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name="MATE")
    return {"secret": secret, "uri": uri}


class MFAEnableRequest(BaseModel):
    secret: str
    code: str


@router.post("/auth/mfa/enable")
async def mfa_enable(
    body: MFAEnableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify TOTP code and enable MFA on the account."""
    totp = pyotp.TOTP(body.secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Código inválido")
    current_user.totp_secret = body.secret
    current_user.totp_enabled = True
    await db.commit()
    return {"status": "mfa_enabled"}


class MFADisableRequest(BaseModel):
    code: str


@router.post("/auth/mfa/disable")
async def mfa_disable(
    body: MFADisableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disable MFA after verifying current TOTP code."""
    if not current_user.totp_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="MFA no está activo")
    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Código inválido")
    current_user.totp_secret = None
    current_user.totp_enabled = False
    await db.commit()
    return {"status": "mfa_disabled"}


class MFAValidateRequest(BaseModel):
    mfa_token: str
    code: str


@router.post("/auth/mfa/validate")
async def mfa_validate(
    body: MFAValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete login: verify TOTP code using the temporary mfa_token."""
    from sqlalchemy import select
    user_id = _verify_mfa_token(body.mfa_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token MFA inválido o expirado")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="Usuario no válido")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=401, detail="Código inválido")

    token = create_token(user.id, user.email)
    return {"token": token, "name": user.name, "email": user.email}


def make_mfa_token(user_id: str) -> str:
    return _make_mfa_token(user_id)
