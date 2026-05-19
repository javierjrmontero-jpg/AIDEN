from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.llm.client import stream_chat
from typing import List

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

@router.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        stream_chat(request.messages),
        media_type="text/event-stream"
    )
