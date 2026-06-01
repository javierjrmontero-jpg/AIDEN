from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.calendar_config import CalendarConfig
from app.services.calendar.service import (
    list_upcoming_events,
    create_event,
    get_account_email,
)

router = APIRouter()


class CalendarConfigCreate(BaseModel):
    refresh_token: str
    calendar_id: Optional[str] = "primary"


class EventCreate(BaseModel):
    summary: str
    start: str  # ISO 8601: "2026-06-01T18:00:00" o "2026-06-01" (día completo)
    end: Optional[str] = ""
    description: Optional[str] = ""
    location: Optional[str] = ""
    account_id: Optional[str] = None


@router.get("/calendar/config")
async def get_calendar_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CalendarConfig)
        .where(CalendarConfig.user_id == current_user.id)
        .order_by(CalendarConfig.created_at.asc())
    )
    configs = result.scalars().all()
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "google_email": c.google_email,
            "calendar_id": c.calendar_id,
            "enabled": c.enabled,
        }
        for c in configs
    ]


@router.post("/calendar/config")
async def add_calendar_config(
    request: CalendarConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Valida el refresh_token contra Google y obtiene el email de la cuenta
    try:
        google_email = await get_account_email(request.refresh_token)
    except Exception as ex:
        raise HTTPException(400, f"Refresh token inválido o sin permisos: {ex}")

    result = await db.execute(
        select(CalendarConfig)
        .where(CalendarConfig.user_id == current_user.id)
        .where(CalendarConfig.google_email == google_email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.refresh_token = request.refresh_token
        existing.calendar_id = request.calendar_id or "primary"
        existing.enabled = True
        existing.updated_at = datetime.utcnow()
    else:
        db.add(
            CalendarConfig(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                provider="google",
                google_email=google_email,
                refresh_token=request.refresh_token,
                calendar_id=request.calendar_id or "primary",
            )
        )

    await db.commit()
    return {"status": "saved", "google_email": google_email}


@router.delete("/calendar/config/{config_id}")
async def delete_calendar_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        delete(CalendarConfig)
        .where(CalendarConfig.id == config_id)
        .where(CalendarConfig.user_id == current_user.id)
    )
    await db.commit()
    return {"status": "deleted"}


@router.get("/calendar/events")
async def get_events(
    days: int = 7,
    limit: int = 10,
    account_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(CalendarConfig).where(CalendarConfig.user_id == current_user.id)
    if account_id:
        query = query.where(CalendarConfig.id == account_id)
    else:
        query = query.where(CalendarConfig.enabled == True)

    result = await db.execute(query)
    configs = result.scalars().all()
    if not configs:
        raise HTTPException(400, "No hay calendarios conectados")

    all_events = []
    for config in configs:
        try:
            events = await list_upcoming_events(config, max_results=limit, days_ahead=days)
            for e in events:
                e["account"] = config.google_email
                e["account_id"] = config.id
            all_events.extend(events)
        except Exception as ex:
            all_events.append(
                {
                    "id": "error",
                    "summary": f"Error al conectar con {config.google_email}",
                    "start": "",
                    "end": "",
                    "account": config.google_email,
                    "account_id": config.id,
                    "error": True,
                    "description": str(ex),
                }
            )

    all_events.sort(key=lambda e: e.get("start") or "")
    return all_events


@router.post("/calendar/events")
async def create_event_endpoint(
    request: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.account_id:
        result = await db.execute(
            select(CalendarConfig)
            .where(CalendarConfig.id == request.account_id)
            .where(CalendarConfig.user_id == current_user.id)
        )
    else:
        result = await db.execute(
            select(CalendarConfig)
            .where(CalendarConfig.user_id == current_user.id)
            .where(CalendarConfig.enabled == True)
            .limit(1)
        )

    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(400, "No hay calendarios conectados")

    try:
        created = await create_event(
            config,
            summary=request.summary,
            start_iso=request.start,
            end_iso=request.end or "",
            description=request.description or "",
            location=request.location or "",
        )
    except Exception as ex:
        raise HTTPException(400, f"Error al crear el evento: {ex}")

    return {"status": "created", "event": created}
