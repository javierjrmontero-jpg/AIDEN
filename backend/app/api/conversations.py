from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.conversation.service import (
    get_conversations, get_messages, create_conversation, delete_conversation
)

router = APIRouter()

@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    convs = await get_conversations(db)
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
async def new_conversation(db: AsyncSession = Depends(get_db)):
    conv = await create_conversation(db)
    return {"id": conv.id, "title": conv.title}

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    msgs = await get_messages(db, conversation_id)
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
async def remove_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    await delete_conversation(db, conversation_id)
    return {"status": "deleted"}
