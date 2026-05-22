from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.memory import Memory
import os
import shutil
from datetime import datetime, timedelta

router = APIRouter()

async def require_admin(current_user: User = Depends(get_current_user)):
    # Por ahora el primer usuario registrado es admin
    # En el futuro se puede agregar un campo is_admin
    return current_user

@router.get("/admin/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    # Usuarios
    users_count = await db.scalar(select(func.count(User.id)))

    # Conversaciones
    convs_count = await db.scalar(select(func.count(Conversation.id)))

    # Mensajes
    msgs_count = await db.scalar(select(func.count(Message.id)))

    # Documentos
    docs_count = await db.scalar(select(func.count(Document.id)))

    # Memorias
    memories_count = await db.scalar(select(func.count(Memory.id)))

    # Conversaciones últimas 7 días
    week_ago = datetime.utcnow() - timedelta(days=7)
    convs_week = await db.scalar(
        select(func.count(Conversation.id))
        .where(Conversation.created_at >= week_ago)
    )

    # Tamaño de la DB
    db_path = "/data/db/aiden.db"
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    # Tamaño del vectorDB
    vectordb_path = "/data/vectordb"
    vectordb_size = 0
    if os.path.exists(vectordb_path):
        for dirpath, dirnames, filenames in os.walk(vectordb_path):
            for f in filenames:
                vectordb_size += os.path.getsize(os.path.join(dirpath, f))

    return {
        "users": users_count,
        "conversations": convs_count,
        "conversations_this_week": convs_week,
        "messages": msgs_count,
        "documents": docs_count,
        "memories": memories_count,
        "db_size_mb": round(db_size / (1024 * 1024), 2),
        "vectordb_size_mb": round(vectordb_size / (1024 * 1024), 2),
    }

@router.get("/admin/users")
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role or "",
            "created_at": u.created_at.isoformat(),
            "is_active": u.is_active
        }
        for u in users
    ]

@router.get("/admin/conversations")
async def get_all_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    result = await db.execute(
        select(Conversation, User.name.label("user_name"))
        .join(User, Conversation.user_id == User.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    rows = result.all()
    return [
        {
            "id": row.Conversation.id,
            "title": row.Conversation.title,
            "user_name": row.user_name,
            "created_at": row.Conversation.created_at.isoformat(),
            "updated_at": row.Conversation.updated_at.isoformat()
        }
        for row in rows
    ]

from app.models.usage import SearchUsage

@router.get("/admin/search-usage")
async def get_search_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    # Total de búsquedas
    total = await db.scalar(select(func.count(SearchUsage.id))) or 0

    # Esta semana
    week_ago = datetime.utcnow() - timedelta(days=7)
    this_week = await db.scalar(
        select(func.count(SearchUsage.id))
        .where(SearchUsage.created_at >= week_ago)
    ) or 0

    # Este mes
    month_ago = datetime.utcnow() - timedelta(days=30)
    this_month = await db.scalar(
        select(func.count(SearchUsage.id))
        .where(SearchUsage.created_at >= month_ago)
    ) or 0

    # Costo estimado (USD 5 por 1000 requests)
    cost_month = round((this_month / 1000) * 5.0, 4)
    cost_total = round((total / 1000) * 5.0, 4)

    # Crédito mensual gratuito de Brave = USD 5 = 1000 requests
    free_remaining = max(0, 1000 - this_month)
    free_pct = round((free_remaining / 1000) * 100, 1)

    return {
        "total_searches": total,
        "searches_this_week": this_week,
        "searches_this_month": this_month,
        "cost_this_month_usd": cost_month,
        "cost_total_usd": cost_total,
        "free_tier_remaining": free_remaining,
        "free_tier_percentage": free_pct,
        "free_tier_limit": 1000
    }

import subprocess

@router.post("/admin/backup")
async def trigger_backup(
    current_user: User = Depends(require_admin)
):
    try:
        result = subprocess.run(
            ["/home/jmontero/aiden/scripts/backup.sh"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return {"status": "success", "output": result.stdout}
        else:
            return {"status": "error", "output": result.stderr}
    except Exception as e:
        raise HTTPException(500, f"Error ejecutando backup: {str(e)}")

@router.get("/admin/backups")
async def list_backups(
    current_user: User = Depends(require_admin)
):
    import glob
    backup_dir = "/home/jmontero/mate_backups"
    files = sorted(glob.glob(f"{backup_dir}/mate_backup_*.tar.gz"), reverse=True)
    backups = []
    for f in files[:10]:
        stat = os.stat(f)
        backups.append({
            "filename": os.path.basename(f),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    return backups