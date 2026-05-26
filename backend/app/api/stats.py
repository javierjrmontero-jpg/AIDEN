from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.task import Task
from app.models.memory import Memory
from app.models.document import Document
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/stats/personal")
async def get_personal_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Conversaciones totales
    total_convs = await db.scalar(
        select(func.count(Conversation.id))
        .where(Conversation.user_id == current_user.id)
    ) or 0

    # Conversaciones esta semana
    convs_week = await db.scalar(
        select(func.count(Conversation.id))
        .where(Conversation.user_id == current_user.id)
        .where(Conversation.created_at >= week_ago)
    ) or 0

    # Conversaciones este mes
    convs_month = await db.scalar(
        select(func.count(Conversation.id))
        .where(Conversation.user_id == current_user.id)
        .where(Conversation.created_at >= month_ago)
    ) or 0

    # Mensajes totales
    total_msgs = await db.scalar(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == current_user.id)
    ) or 0

    # Mensajes del usuario vs MATE
    user_msgs = await db.scalar(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == current_user.id)
        .where(Message.role == "user")
    ) or 0

    # Tareas
    total_tasks = await db.scalar(
        select(func.count(Task.id))
        .where(Task.user_id == current_user.id)
    ) or 0

    completed_tasks = await db.scalar(
        select(func.count(Task.id))
        .where(Task.user_id == current_user.id)
        .where(Task.completed == True)
    ) or 0

    # Actividad por día (últimos 7 días)
    daily_activity = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        count = await db.scalar(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == current_user.id)
            .where(Conversation.created_at >= day_start)
            .where(Conversation.created_at <= day_end)
        ) or 0

        daily_activity.append({
            "day": day.strftime("%a"),
            "date": day.strftime("%d/%m"),
            "conversations": count
        })

    # Documentos
    total_docs = await db.scalar(
        select(func.count(Document.id))
        .where(Document.user_id == current_user.id)
    ) or 0

    # Memorias
    total_memories = await db.scalar(
        select(func.count(Memory.id))
        .where(Memory.user_id == current_user.id)
    ) or 0

    # Día más activo
    most_active = max(daily_activity, key=lambda x: x["conversations"]) if daily_activity else None

    return {
        "conversations": {
            "total": total_convs,
            "this_week": convs_week,
            "this_month": convs_month,
        },
        "messages": {
            "total": total_msgs,
            "by_user": user_msgs,
            "by_mate": total_msgs - user_msgs,
        },
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "pending": total_tasks - completed_tasks,
            "completion_rate": round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
        },
        "documents": total_docs,
        "memories": total_memories,
        "daily_activity": daily_activity,
        "most_active_day": most_active,
        "member_since": current_user.created_at.strftime("%d/%m/%Y")
    }