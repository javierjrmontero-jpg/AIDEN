from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.conversation.service import (
    get_conversations, get_messages, create_conversation, delete_conversation
)

router = APIRouter()

@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    convs = await get_conversations(db, current_user.id)
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat()
        }
        for c in convs
    ]

@router.post("/conversations")
async def new_conversation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = await create_conversation(db, current_user.id)
    return {"id": conv.id, "title": conv.title}

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    msgs = await get_messages(db, conversation_id, current_user.id)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        }
        for m in msgs
    ]

@router.delete("/conversations/{conversation_id}")
async def remove_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await delete_conversation(db, conversation_id, current_user.id)
    return {"status": "deleted"}
