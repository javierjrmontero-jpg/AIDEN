"""
POST /api/v1/tasks/prioritize
==============================
Toma las tareas pendientes del usuario, las cruza con el calendario
de los próximos 7 días y emails recientes, y devuelve una lista
reordenada con justificación generada por Claude Haiku.

Respuesta:
  {
    "prioritized": [
      { "id": "...", "title": "...", "priority": "high", "due_date": "...",
        "rank": 1, "reason": "..." },
      ...
    ],
    "summary": "Texto ejecutivo con el orden sugerido.",
    "generated_at": "..."
  }

Invocable desde chat con comando de voz "priorizar mis tareas".
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic, os, json

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.task import Task
from app.models.calendar_config import CalendarConfig
from app.models.email_config import EmailConfig
from app.services.calendar.router import list_events_range
from app.services.email.service import fetch_unread

router = APIRouter()

ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
MODEL = "claude-haiku-4-5-20251001"


def _task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description or "",
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "priority": t.priority,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


async def _prioritize_with_claude(tasks: list, events: list, unread_emails: list) -> dict:
    now = datetime.now()

    tasks_text = "\n".join(
        f"- [{t['priority'].upper()}] {t['title']}"
        f"{' | vence: ' + t['due_date'][:10] if t['due_date'] else ''}"
        f"{' | ' + t['description'][:80] if t['description'] else ''}"
        for t in tasks
    )

    events_text = "\n".join(
        f"- {e.get('summary', 'Evento')} ({e.get('start', '')[:16]})"
        for e in events[:10]
    ) or "Sin eventos próximos."

    email_text = ", ".join(
        m.get("from", "").split("<")[0].strip()
        for m in unread_emails[:5]
    ) or "Sin emails urgentes."

    prompt = f"""Sos el asistente de productividad de Javier. Hoy es {now.strftime('%A %d de %B de %Y')}.

TAREAS PENDIENTES:
{tasks_text}

AGENDA PRÓXIMOS 7 DÍAS:
{events_text}

EMAILS NO LEÍDOS (remitentes): {email_text}

Reordenar las tareas de mayor a menor urgencia considerando:
1. Fecha de vencimiento (más próxima = más urgente)
2. Prioridad declarada (high > medium > low)
3. Contexto de la agenda (si hay un evento relacionado esta semana, sube el orden)
4. Emails pendientes que podrían estar relacionados

Respondé SOLO con un JSON válido en este formato exacto:
{{
  "order": ["título tarea 1", "título tarea 2", ...],
  "reasons": {{"título tarea 1": "razón breve", "título tarea 2": "razón breve", ...}},
  "summary": "Una oración ejecutiva con el orden sugerido."
}}"""

    try:
        response = ANTHROPIC_CLIENT.messages.create(
            model=MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Extraer JSON aunque haya texto extra
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception as e:
        # Fallback: orden por due_date + priority
        return {
            "order": [t["title"] for t in tasks],
            "reasons": {t["title"]: "Orden por vencimiento y prioridad." for t in tasks},
            "summary": f"Tenés {len(tasks)} tareas pendientes ordenadas por vencimiento."
        }


@router.post("/tasks/prioritize")
async def prioritize_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    # ── Tareas pendientes ─────────────────────────────────────────────────────
    result = await db.execute(
        select(Task)
        .where(Task.user_id == current_user.id)
        .where(Task.completed == False)
        .order_by(Task.due_date.asc().nullslast(), Task.priority.desc())
        .limit(20)
    )
    tasks = [_task_to_dict(t) for t in result.scalars().all()]

    if not tasks:
        return {
            "prioritized": [],
            "summary": "No tenés tareas pendientes.",
            "generated_at": now.isoformat(),
        }

    # ── Calendario próximos 7 días ────────────────────────────────────────────
    events = []
    try:
        cal_result = await db.execute(
            select(CalendarConfig)
            .where(CalendarConfig.user_id == current_user.id)
            .where(CalendarConfig.enabled == True)
        )
        for cal_cfg in cal_result.scalars().all():
            events.extend(await list_events_range(
                cal_cfg,
                time_min=now.isoformat(),
                time_max=(now + timedelta(days=7)).isoformat(),
                max_results=20,
            ))
        events.sort(key=lambda e: e.get("start") or "")
    except Exception:
        pass

    # ── Emails no leídos ──────────────────────────────────────────────────────
    unread = []
    try:
        email_result = await db.execute(
            select(EmailConfig)
            .where(EmailConfig.user_id == current_user.id)
            .where(EmailConfig.enabled == True)
        )
        for cfg in email_result.scalars().all():
            try:
                unread.extend(await fetch_unread(cfg, limit=10))
            except Exception:
                pass
    except Exception:
        pass

    # ── Priorizar con Claude ──────────────────────────────────────────────────
    result_data = await _prioritize_with_claude(tasks, events, unread)

    # Reconstruir lista en el orden sugerido
    task_map = {t["title"]: t for t in tasks}
    ordered_titles = result_data.get("order", [t["title"] for t in tasks])
    reasons = result_data.get("reasons", {})

    prioritized = []
    rank = 1
    for title in ordered_titles:
        if title in task_map:
            t = task_map[title]
            prioritized.append({**t, "rank": rank, "reason": reasons.get(title, "")})
            rank += 1
    # Agregar las que Claude no incluyó (por si acaso)
    included = {t["title"] for t in prioritized}
    for t in tasks:
        if t["title"] not in included:
            prioritized.append({**t, "rank": rank, "reason": "Sin análisis adicional."})
            rank += 1

    return {
        "prioritized": prioritized,
        "summary": result_data.get("summary", ""),
        "generated_at": now.isoformat(),
    }
