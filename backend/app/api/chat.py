from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm.client import stream_chat
from app.services.conversation.service import (
    create_conversation, save_message
)
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

async def stream_and_save(messages, conversation_id, user_id, db):
    full_response = ""
    order = len(messages)

    user_msg = messages[-1]
    await save_message(db, conversation_id, user_msg.role, user_msg.content, order - 1)

    async for chunk in stream_chat(messages):
        if chunk.startswith("data: ") and chunk.strip() != "data: [DONE]":
            text = chunk[6:].replace("\\n", "\n").rstrip("\n\n")
            full_response += text
        yield chunk

    if full_response:
        await save_message(db, conversation_id, "assistant", full_response, order)

    yield f"data: [CONV:{conversation_id}]\n\n"

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
        stream_and_save(request.messages, conversation_id, current_user.id, db),
        media_type="text/event-stream"
    )
