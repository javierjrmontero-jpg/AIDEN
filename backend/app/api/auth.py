import hashlib
import hmac
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
from app.core.config import settings
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.auth.service import (
    get_user_by_email, create_user, verify_password, create_token
)

_MATE_BASE = "https://mate.molmont.com.ar"


def _make_approval_token(user_id: str, action: str) -> str:
    ts = str(int(time.time()))
    msg = f"{user_id}:{action}:{ts}"
    sig = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}:{sig}"


def _verify_approval_token(token: str) -> tuple[str, str] | None:
    """Returns (user_id, action) or None if invalid/expired."""
    try:
        user_id, action, ts, sig = token.rsplit(":", 3)
        msg = f"{user_id}:{action}:{ts}"
        expected = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if time.time() - int(ts) > settings.APPROVAL_TOKEN_TTL:
            return None
        if action not in ("approve", "reject"):
            return None
        return user_id, action
    except Exception:
        return None


async def _notify_n8n_registration(user_id: str, email: str, name: str) -> None:
    if not settings.N8N_REGISTRATION_WEBHOOK:
        return
    approve_token = _make_approval_token(user_id, "approve")
    reject_token = _make_approval_token(user_id, "reject")
    payload = {
        "event": "user_registration",
        "user_id": user_id,
        "email": email,
        "name": name,
        "approve_url": f"{_MATE_BASE}/api/v1/auth/approve/{approve_token}",
        "reject_url": f"{_MATE_BASE}/api/v1/auth/reject/{reject_token}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(settings.N8N_REGISTRATION_WEBHOOK, json=payload)
    except Exception:
        pass  # no bloquear el registro si n8n no responde

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _validate_password(v: str) -> None:
    """NIST SP 800-63B + OWASP: mínimo 8 chars, mayúscula, minúscula, número y carácter especial."""
    errors = []
    if len(v) < 8:
        errors.append("al menos 8 caracteres")
    if not any(c.isupper() for c in v):
        errors.append("al menos una mayúscula")
    if not any(c.islower() for c in v):
        errors.append("al menos una minúscula")
    if not any(c.isdigit() for c in v):
        errors.append("al menos un número")
    if not any(c in r"""!@#$%^&*()_+-=[]{}|;':",.<>?/`~\\""" for c in v):
        errors.append("al menos un carácter especial (!@#$%...)")
    if errors:
        raise ValueError("La contraseña debe tener: " + ", ".join(errors))


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        _validate_password(v)
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        _validate_password(v)
        return v


@router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user = await create_user(db, body.email, body.name, body.password)
    # Deshabilitar hasta que el admin apruebe
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    await _notify_n8n_registration(user.id, user.email, user.name)
    return {"pending": True, "message": "Registro exitoso. Tu cuenta será revisada por el administrador."}


@router.get("/auth/approve/{token}", response_class=HTMLResponse)
async def approve_user(token: str, db: AsyncSession = Depends(get_db)):
    result = _verify_approval_token(token)
    if not result:
        return HTMLResponse("<h2>Link inválido o expirado.</h2>", status_code=400)
    user_id, action = result
    from sqlalchemy import select
    row = await db.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    if not user:
        return HTMLResponse("<h2>Usuario no encontrado.</h2>", status_code=404)
    if action == "approve":
        user.is_active = True
        await db.commit()
        return HTMLResponse(f"<h2>✅ Usuario <b>{user.email}</b> aprobado. Ya puede ingresar a MATE.</h2>")
    else:
        await db.delete(user)
        await db.commit()
        return HTMLResponse(f"<h2>❌ Usuario <b>{user.email}</b> rechazado y eliminado.</h2>")


@router.get("/auth/reject/{token}", response_class=HTMLResponse)
async def reject_user(token: str, db: AsyncSession = Depends(get_db)):
    return await approve_user(token, db)


@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tu cuenta está pendiente de aprobación por el administrador")
    if user.totp_enabled:
        from app.api.mfa import make_mfa_token
        return {"mfa_required": True, "mfa_token": make_mfa_token(user.id)}
    token = create_token(user.id, user.email)
    return {"token": token, "name": user.name, "email": user.email}


@router.get("/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "name": current_user.name}


class ProfileUpdate(BaseModel):
    role: str = ""
    context: str = ""
    preferences: str = ""
    language: str = "es"


@router.get("/auth/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role or "",
        "context": current_user.context or "",
        "preferences": current_user.preferences or "",
        "language": current_user.language or "es",
        "is_admin": current_user.is_admin or False,
    }


@router.put("/auth/profile")
async def update_profile(
    request: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.role = request.role
    current_user.context = request.context
    current_user.preferences = request.preferences
    current_user.language = request.language
    await db.commit()
    return {"status": "updated"}


class InviteRequest(BaseModel):
    email: EmailStr
    name: str


@router.post("/auth/invite")
async def invite_user(
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Solo el administrador puede invitar usuarios")
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    import uuid
    from app.services.auth.service import hash_password
    invited = User(
        id=str(uuid.uuid4()),
        email=body.email,
        name=body.name,
        hashed_password=hash_password(f"INVITE_{uuid.uuid4().hex}_Aa1!"),
    )
    db.add(invited)
    await db.commit()
    return {"status": "invited", "email": body.email, "name": body.name}


@router.put("/auth/password")
async def change_password(
    request: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")
    from app.services.auth.service import hash_password
    current_user.hashed_password = hash_password(request.new_password)
    await db.commit()
    return {"status": "password updated"}
