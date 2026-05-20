from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.conversation import Conversation, Message
from datetime import datetime
import uuid

async def create_conversation(db: AsyncSession, title: str = "Nueva conversación") -> Conversation:
    conv = Conversation(
        id=str(uuid.uuid4()),
        title=title,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv

async def get_conversations(db: AsyncSession) -> list:
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()

async def get_messages(db: AsyncSession, conversation_id: str) -> list:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.order_index)
    )
    return result.scalars().all()

async def save_message(db: AsyncSession, conversation_id: str, role: str, content: str, order: int) -> Message:
    msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
        order_index=order
    )
    db.add(msg)
    # Actualizar timestamp de conversación
    conv = await db.get(Conversation, conversation_id)
    if conv:
        conv.updated_at = datetime.utcnow()
        # Generar título automático del primer mensaje
        if order == 0 and role == "user":
            conv.title = content[:60] + ("..." if len(content) > 60 else "")
    await db.commit()
    return msg

async def delete_conversation(db: AsyncSession, conversation_id: str):
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()
