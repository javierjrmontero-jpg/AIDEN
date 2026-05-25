from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
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
    account_id: Optional[str] = None

@router.get("/email/config")
async def get_email_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EmailConfig)
        .where(EmailConfig.user_id == current_user.id)
        .order_by(EmailConfig.created_at.asc())
    )
    configs = result.scalars().all()
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "email_address": c.email_address,
            "enabled": c.enabled
        }
        for c in configs
    ]

@router.post("/email/config")
async def add_email_config(
    request: EmailConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que no existe ya esa dirección para este usuario
    result = await db.execute(
        select(EmailConfig)
        .where(EmailConfig.user_id == current_user.id)
        .where(EmailConfig.email_address == request.email_address)
    )
    existing = result.scalar_one_or_none()

    provider_defaults = PROVIDER_CONFIG.get(request.provider, {})

    if existing:
        # Actualizar la existente
        existing.provider = request.provider
        existing.app_password = request.app_password
        existing.imap_host = request.imap_host or provider_defaults.get("imap_host")
        existing.imap_port = request.imap_port or provider_defaults.get("imap_port", 993)
        existing.smtp_host = request.smtp_host or provider_defaults.get("smtp_host")
        existing.smtp_port = request.smtp_port or provider_defaults.get("smtp_port", 587)
        existing.updated_at = datetime.utcnow()
    else:
        # Crear nueva
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

@router.delete("/email/config/{config_id}")
async def delete_email_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await db.execute(
        delete(EmailConfig)
        .where(EmailConfig.id == config_id)
        .where(EmailConfig.user_id == current_user.id)
    )
    await db.commit()
    return {"status": "deleted"}

@router.get("/email/inbox")
async def get_inbox(
    limit: int = 10,
    account_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(EmailConfig).where(EmailConfig.user_id == current_user.id)
    if account_id:
        query = query.where(EmailConfig.id == account_id)
    else:
        query = query.where(EmailConfig.enabled == True)

    result = await db.execute(query)
    configs = result.scalars().all()

    if not configs:
        raise HTTPException(400, "No hay cuentas de email configuradas")

    all_emails = []
    for config in configs:
        try:
            emails = await fetch_inbox(config, limit)
            for e in emails:
                e["account"] = config.email_address
                e["account_id"] = config.id
            all_emails.extend(emails)
        except Exception as ex:
            all_emails.append({
                "id": "error",
                "subject": f"Error al conectar con {config.email_address}",
                "from": "Sistema",
                "date": "",
                "body": str(ex),
                "account": config.email_address,
                "account_id": config.id,
                "error": True
            })

    return all_emails

@router.get("/email/unread")
async def get_unread(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(EmailConfig)
        .where(EmailConfig.user_id == current_user.id)
        .where(EmailConfig.enabled == True)
    )
    configs = result.scalars().all()
    if not configs:
        return []

    all_unread = []
    for config in configs:
        try:
            unread = await fetch_unread(config)
            for e in unread:
                e["account"] = config.email_address
            all_unread.extend(unread)
        except Exception:
            pass

    return all_unread

@router.post("/email/send")
async def send_email_endpoint(
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if request.account_id:
        result = await db.execute(
            select(EmailConfig)
            .where(EmailConfig.id == request.account_id)
            .where(EmailConfig.user_id == current_user.id)
        )
    else:
        result = await db.execute(
            select(EmailConfig)
            .where(EmailConfig.user_id == current_user.id)
            .where(EmailConfig.enabled == True)
            .limit(1)
        )

    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(400, "No hay cuentas de email configuradas")

    await send_email(config, request.to, request.subject, request.body)
    return {"status": "sent"}