from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.memory import Memory
from app.models.conversation import Message as ConvMessage
from app.services.memory.service import (
    get_memories, delete_memory, extract_and_save_memories
)

router = APIRouter()

@router.get("/memories")
async def list_memories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    memories = await get_memories(db, current_user.id, limit=50)
    return [
        {
            "id": m.id,
            "content": m.content,
            "category": m.category,
            "importance": m.importance,
            "created_at": m.created_at.isoformat()
        }
        for m in memories
    ]

@router.delete("/memories/{memory_id}")
async def remove_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await delete_memory(db, memory_id, current_user.id)
    return {"status": "deleted"}

@router.post("/memories/extract/{conversation_id}")
async def extract_memories(
    conversation_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Obtener mensajes de la conversación
    result = await db.execute(
        select(ConvMessage)
        .where(ConvMessage.conversation_id == conversation_id)
        .order_by(ConvMessage.order_index)
    )
    messages = result.scalars().all()
    msgs_data = [{"role": m.role, "content": m.content} for m in messages]

    count = await extract_and_save_memories(
        db, current_user.id, conversation_id, msgs_data
    )
    return {"extracted": count}
