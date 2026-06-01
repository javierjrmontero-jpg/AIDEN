from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.llm.client import stream_chat
from app.services.conversation.service import create_conversation, save_message
from app.services.memory.service import extract_and_save_memories
from app.models.conversation import Message as ConvMessage
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from typing import List, Optional

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    conversation_id: Optional[str] = None

async def stream_and_save(messages, conversation_id, user, db):
    full_response = ""
    order = len(messages)

    user_msg = messages[-1]
    await save_message(db, conversation_id, user_msg.role, user_msg.content, order - 1)

    async for chunk in stream_chat(messages, user, db):
        if chunk.startswith("data: ") and chunk.strip() not in ["data: [DONE]"]:
            try:
                text = __import__('json').loads(chunk[6:])
                if isinstance(text, str) and not text.startswith("[STATUS:"):
                    full_response += text
            except Exception:
                pass
        yield chunk

    if full_response:
        await save_message(db, conversation_id, "assistant", full_response, order)

    # Extraer memorias en background si la conversación tiene suficiente contenido
    if len(messages) >= 3:
        try:
            result = await db.execute(
                select(ConvMessage)
                .where(ConvMessage.conversation_id == conversation_id)
                .order_by(ConvMessage.order_index)
            )
            all_messages = result.scalars().all()
            msgs_data = [{"role": m.role, "content": m.content} for m in all_messages]
            await extract_and_save_memories(db, user.id, conversation_id, msgs_data)
        except Exception as e:
            pass

    yield f"data: {__import__('json').dumps('[CONV:' + conversation_id + ']')}\n\n"

@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conversation_id = request.conversation_id
    if not conversation_id:
        conv = await create_conversation(db, current_user.id)
        conversation_id = conv.id

    return StreamingResponse(
        stream_and_save(request.messages, conversation_id, current_user, db),
        media_type="text/event-stream"
    )