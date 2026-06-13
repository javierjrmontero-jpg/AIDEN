from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.user_settings import UserSettings

router = APIRouter(tags=["settings"])


class SettingsOut(BaseModel):
    assistant_name: str
    theme: str


class SettingsIn(BaseModel):
    assistant_name: Optional[str] = None
    theme: Optional[str] = None


async def _get_or_create(db: AsyncSession, user_id: int) -> UserSettings:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        s = UserSettings(user_id=user_id, assistant_name="MATE", theme="dark")
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return s


@router.get("/settings", response_model=SettingsOut)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _get_or_create(db, current_user.id)
    return SettingsOut(
        assistant_name=s.assistant_name or "MATE",
        theme=s.theme or "dark",
    )


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    data: SettingsIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await _get_or_create(db, current_user.id)
    if data.assistant_name is not None:
        s.assistant_name = data.assistant_name.strip() or "MATE"
    if data.theme is not None:
        s.theme = data.theme
    await db.commit()
    await db.refresh(s)
    return SettingsOut(
        assistant_name=s.assistant_name or "MATE",
        theme=s.theme or "dark",
    )
