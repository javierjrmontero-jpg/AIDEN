from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.email_config import EmailConfig
from app.services.email.service import fetch_inbox, fetch_unread, send_email, PROVIDER_CONFIG
from datetime import datetime
import uuid

router = APIRouter()

class EmailConfigCreate(BaseModel):
    provider: str
    email_address: str
    app_password: str
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None

class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str

@router.get("/email/config")
async def get_email_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EmailConfig).where(EmailConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "provider": config.provider,
        "email_address": config.email_address,
        "enabled": config.enabled
    }

@router.post("/email/config")
async def save_email_config(
    request: EmailConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EmailConfig).where(EmailConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()

    provider_defaults = PROVIDER_CONFIG.get(request.provider, {})

    if config:
        config.provider = request.provider
        config.email_address = request.email_address
        config.app_password = request.app_password
        config.imap_host = request.imap_host or provider_defaults.get("imap_host")
        config.imap_port = request.imap_port or provider_defaults.get("imap_port", 993)
        config.smtp_host = request.smtp_host or provider_defaults.get("smtp_host")
        config.smtp_port = request.smtp_port or provider_defaults.get("smtp_port", 587)
        config.updated_at = datetime.utcnow()
    else:
        config = EmailConfig(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            provider=request.provider,
            email_address=request.email_address,
            app_password=request.app_password,
            imap_host=request.imap_host or provider_defaults.get("imap_host"),
            imap_port=request.imap_port or provider_defaults.get("imap_port", 993),
            smtp_host=request.smtp_host or provider_defaults.get("smtp_host"),
            smtp_port=request.smtp_port or provider_defaults.get("smtp_port", 587),
        )
        db.add(config)

    await db.commit()
    return {"status": "saved"}

@router.get("/email/inbox")
async def get_inbox(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EmailConfig).where(EmailConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(400, "Email no configurado")

    emails = await fetch_inbox(config, limit)
    return emails

@router.get("/email/unread")
async def get_unread(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EmailConfig).where(EmailConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(400, "Email no configurado")

    emails = await fetch_unread(config)
    return emails

@router.post("/email/send")
async def send_email_endpoint(
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EmailConfig).where(EmailConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(400, "Email no configurado")

    await send_email(config, request.to, request.subject, request.body)
    return {"status": "sent"}