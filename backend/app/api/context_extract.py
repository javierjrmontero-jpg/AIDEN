"""
MATE — Extractor de contexto acumulativo (F4-5)
===============================================
Analiza conversaciones recientes con Claude Haiku y extrae compromisos
del usuario que aún no están en el sistema de tareas.

POST /api/v1/conversations/extract-tasks?days=7&dry_run=false
  → analiza todas las conversaciones de los últimos N días

POST /api/v1/conversations/{conversation_id}/extract-tasks?dry_run=false
  → analiza una conversación específica

Respuesta:
  {
    "extracted": N,     # compromisos encontrados
    "created": N,       # tareas nuevas creadas
    "skipped": N,       # ya existían (deduplicadas)
    "tasks": [...],     # detalle de lo creado
    "conversations_analyzed": N,
    "generated_at": "..."
  }
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic, os, json, uuid, re

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.task import Task
from app.models.conversation import Conversation, Message

router = APIRouter()

ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
MODEL = "claude-haiku-4-5-20251001"

EXTRACT_SYSTEM = """Sos un extractor de compromisos de conversaciones en español argentino.
Analizá el historial dado y extraé SOLO los compromisos explícitos del USUARIO (no del asistente), como:
- Cosas que el usuario dijo que va a hacer ("voy a...", "tengo que...", "necesito...", "me comprometí a...")
- Recordatorios que el usuario pidió ("recordame que...", "no me olvides de...", "acordate de...")
- Plazos o fechas límite mencionados por el usuario

Devolvé ÚNICAMENTE un array JSON válido. Cada elemento debe tener:
- "title": string conciso (máximo 80 caracteres), accionable
- "due_date": "YYYY-MM-DD" si se mencionó alguna fecha, null si no
- "priority": "high" si es urgente/importante, "medium" por defecto, "low" si es a largo plazo

Si no hay compromisos claros, devolvé [].
No inventes compromisos que no estén explícitos. Solo devolvés JSON, sin texto adicional."""


def _normalize(text: str) -> str:
    """Normaliza texto para comparación (deduplicación)."""
    return re.sub(r"[^a-záéíóúüñ0-9 ]", "", text.lower().strip())


def _is_duplicate(title: str, existing_titles: list[str], threshold: float = 0.6) -> bool:
    """True si el título es muy similar a alguna tarea existente."""
    norm_new = _normalize(title)
    words_new = set(norm_new.split())
    for existing in existing_titles:
        norm_ex = _normalize(existing)
        words_ex = set(norm_ex.split())
        if not words_new or not words_ex:
            continue
        intersection = words_new & words_ex
        union = words_new | words_ex
        jaccard = len(intersection) / len(union)
        if jaccard >= threshold:
            return True
    return False


async def _extract_from_messages(messages: list[dict]) -> list[dict]:
    """Llama a Claude Haiku para extraer compromisos de una lista de mensajes."""
    if not messages:
        return []

    # Solo mensajes de usuario para reducir tokens
    user_msgs = [m for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return []

    convo_text = "\n".join(
        f"Usuario: {m['content'][:300]}"
        for m in user_msgs[-30:]  # últimos 30 mensajes de usuario
    )

    try:
        response = ANTHROPIC_CLIENT.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": f"Conversación:\n{convo_text}"}],
        )
        raw = response.content[0].text.strip()
        # Extraer JSON del response
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(raw)
    except Exception:
        return []


async def _process_conversations(
    conversations: list,
    db: AsyncSession,
    user_id: str,
    dry_run: bool,
) -> dict:
    # Cargar títulos de tareas existentes para deduplicación
    existing_result = await db.execute(
        select(Task.title).where(Task.user_id == user_id, Task.completed == False)
    )
    existing_titles = [row[0] for row in existing_result.all()]

    all_extracted = []
    created_tasks = []
    skipped = 0

    for conv in conversations:
        msgs_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.order_index)
        )
        messages = [
            {"role": m.role, "content": m.content}
            for m in msgs_result.scalars().all()
        ]

        extracted = await _extract_from_messages(messages)
        all_extracted.extend(extracted)

        for item in extracted:
            title = item.get("title", "").strip()
            if not title:
                continue

            # Deduplicar
            if _is_duplicate(title, existing_titles + [t["title"] for t in created_tasks]):
                skipped += 1
                continue

            due_date = None
            if item.get("due_date"):
                try:
                    due_date = datetime.strptime(item["due_date"], "%Y-%m-%d")
                except Exception:
                    pass

            priority = item.get("priority", "medium")
            if priority not in ("high", "medium", "low"):
                priority = "medium"

            task_data = {
                "id": str(uuid.uuid4()),
                "title": title,
                "due_date": due_date.isoformat() if due_date else None,
                "priority": priority,
                "source_conversation": conv.id,
            }

            if not dry_run:
                new_task = Task(
                    id=task_data["id"],
                    user_id=user_id,
                    title=title,
                    description=f"Extraído de conversación: {conv.title or conv.id[:8]}",
                    due_date=due_date,
                    priority=priority,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(new_task)

            created_tasks.append(task_data)

    if not dry_run and created_tasks:
        await db.commit()

    return {
        "extracted": len(all_extracted),
        "created": len(created_tasks),
        "skipped": skipped,
        "tasks": created_tasks,
        "conversations_analyzed": len(conversations),
        "generated_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
    }


@router.post("/conversations/extract-tasks")
async def extract_from_recent(
    days: int = 7,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extrae compromisos de conversaciones de los últimos N días."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.updated_at >= cutoff,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(20)
    )
    conversations = result.scalars().all()

    if not conversations:
        return {
            "extracted": 0, "created": 0, "skipped": 0,
            "tasks": [], "conversations_analyzed": 0,
            "generated_at": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
        }

    return await _process_conversations(conversations, db, current_user.id, dry_run)


@router.post("/conversations/{conversation_id}/extract-tasks")
async def extract_from_one(
    conversation_id: str,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extrae compromisos de una conversación específica."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversación no encontrada")

    return await _process_conversations([conv], db, current_user.id, dry_run)
