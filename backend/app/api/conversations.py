from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.conversation.service import (
    get_conversations, get_messages, create_conversation, delete_conversation
)
from app.models.conversation import Conversation, Message
from datetime import datetime

router = APIRouter()

@router.get("/conversations/search")
async def search_conversations(
    q: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not q or len(q) < 2:
        return []

    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .where(Conversation.title.ilike(f"%{q}%"))
        .order_by(Conversation.updated_at.desc())
        .limit(10)
    )
    convs_by_title = conv_result.scalars().all()

    msg_result = await db.execute(
        select(Message.conversation_id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == current_user.id)
        .where(Message.content.ilike(f"%{q}%"))
        .distinct()
        .limit(10)
    )
    conv_ids_by_content = [row[0] for row in msg_result.all()]

    found_ids = {c.id for c in convs_by_title}
    extra_convs = []

    if conv_ids_by_content:
        extra_result = await db.execute(
            select(Conversation)
            .where(Conversation.id.in_(conv_ids_by_content))
            .where(Conversation.id.notin_(found_ids))
        )
        extra_convs = extra_result.scalars().all()

    all_convs = list(convs_by_title) + extra_convs

    return [
        {
            "id": c.id,
            "title": c.title,
            "updated_at": c.updated_at.isoformat(),
            "match_type": "title" if c.id in found_ids else "content"
        }
        for c in all_convs
    ]

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

@router.get("/conversations/{conversation_id}/export/{format}")
async def export_conversation(
    conversation_id: str,
    format: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == current_user.id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversación no encontrada")

    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.order_index)
    )
    messages = msgs_result.scalars().all()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mate_{conv.title[:30].replace(' ', '_')}_{timestamp}"

    if format == "md":
        content = f"# {conv.title}\n\n"
        content += f"*Exportado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — MATE by JJRM*\n\n---\n\n"
        for msg in messages:
            prefix = "**Vos:**" if msg.role == "user" else "**MATE:**"
            content += f"{prefix}\n\n{msg.content}\n\n---\n\n"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={filename}.md"}
        )

    elif format == "txt":
        content = f"{conv.title}\n{'='*50}\n\n"
        for msg in messages:
            prefix = "VOS:" if msg.role == "user" else "MATE:"
            content += f"{prefix}\n{msg.content}\n\n{'-'*30}\n\n"
        return Response(
            content=content.encode("utf-8"),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}.txt"}
        )

    elif format == "json":
        import json
        data = {
            "title": conv.title,
            "exported_at": datetime.now().isoformat(),
            "assistant": "MATE by JJRM",
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "order": m.order_index
                }
                for m in messages
            ]
        }
        return Response(
            content=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}.json"}
        )

    else:
        raise HTTPException(400, "Formato no soportado. Usá: md, txt, json")