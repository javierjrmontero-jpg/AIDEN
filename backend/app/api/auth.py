from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.auth.service import (
    get_user_by_email, create_user, verify_password, create_token
)

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
    token = create_token(user.id, user.email)
    return {"token": token, "name": user.name, "email": user.email}


@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
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
