import anthropic
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.memory import Memory
from app.core.config import settings
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

async def extract_and_save_memories(
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
    messages: list
) -> int:
    """Extrae memorias importantes de una conversación y las guarda."""
    if len(messages) < 2:
        return 0

    # Preparar el texto de la conversación
    conv_text = "\n".join([
        f"{m['role'].upper()}: {m['content']}"
        for m in messages[-10:]  # Últimos 10 mensajes
    ])

    prompt = f"""Analizá esta conversación y extraé información importante que vale la pena recordar sobre el usuario.

CONVERSACIÓN:
{conv_text}

Extraé SOLO información factual y relevante sobre el usuario como:
- Proyectos en los que trabaja
- Tecnologías que usa
- Preferencias o decisiones importantes
- Problemas resueltos o pendientes
- Datos personales o profesionales mencionados

Respondé SOLO con un JSON válido con este formato exacto:
{{
  "memories": [
    {{"content": "descripción concisa de la memoria", "category": "proyecto|tecnologia|preferencia|problema|personal", "importance": 0.8}},
    {{"content": "otra memoria", "category": "categoria", "importance": 0.6}}
  ]
}}

Si no hay nada importante para recordar, respondé: {{"memories": []}}
No incluyas información trivial o de conversaciones genéricas."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        # Limpiar posibles backticks
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        memories = data.get("memories", [])

        saved = 0
        for mem in memories:
            if mem.get("content") and len(mem["content"]) > 10:
                memory = Memory(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    content=mem["content"],
                    category=mem.get("category", "general"),
                    importance=min(1.0, max(0.0, float(mem.get("importance", 0.5)))),
                    source_conversation_id=conversation_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(memory)
                saved += 1

        if saved > 0:
            await db.commit()
            logger.info(f"Guardadas {saved} memorias para usuario {user_id}")

        return saved

    except Exception as e:
        logger.error(f"Error extrayendo memorias: {e}")
        return 0

async def get_memories(db: AsyncSession, user_id: str, limit: int = 10) -> list:
    """Obtiene las memorias más importantes del usuario."""
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.importance.desc(), Memory.updated_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def delete_memory(db: AsyncSession, memory_id: str, user_id: str):
    await db.execute(
        delete(Memory)
        .where(Memory.id == memory_id)
        .where(Memory.user_id == user_id)
    )
    await db.commit()

async def format_memories_for_prompt(db: AsyncSession, user_id: str) -> str:
    memories = await get_memories(db, user_id)
    if not memories:
        return "No hay memorias previas."
    lines = []
    for m in memories:
        lines.append(f"- [{m.category}] {m.content}")
    return "\n".join(lines)
