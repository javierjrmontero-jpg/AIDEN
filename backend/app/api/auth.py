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


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
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
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
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
