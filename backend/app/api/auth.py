from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.services.auth.service import (
    get_user_by_email, create_user, verify_password, create_token
)

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/auth/register")
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, request.email)
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user = await create_user(db, request.email, request.name, request.password)
    token = create_token(user.id, user.email)
    return {"token": token, "name": user.name, "email": user.email}

@router.post("/auth/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, request.email)
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    token = create_token(user.id, user.email)
    return {"token": token, "name": user.name, "email": user.email}

@router.get("/auth/me")
async def me(db: AsyncSession = Depends(get_db)):
    return {"status": "ok"}

from fastapi import Depends
from app.core.auth import get_current_user
from app.models.user import User

class ProfileUpdate(BaseModel):
    role: str = ""
    context: str = ""
    preferences: str = ""

@router.get("/auth/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role or "",
        "context": current_user.context or "",
        "preferences": current_user.preferences or ""
    }

@router.put("/auth/profile")
async def update_profile(
    request: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.role = request.role
    current_user.context = request.context
    current_user.preferences = request.preferences
    await db.commit()
    return {"status": "updated"}
