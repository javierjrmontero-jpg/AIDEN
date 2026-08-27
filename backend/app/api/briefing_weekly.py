"""
GET /api/v1/briefing/weekly
============================
Resumen de la semana pasada para MATE:
  - Eventos de calendario de los últimos 7 días
  - Emails recibidos esta semana (inbox)
  - Tareas completadas y pendientes
  - Genera texto con Claude y lo envía por email

Invocado por 08_weekly.py cada lunes a las 8:00.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic
import os

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.calendar_config import CalendarConfig
from app.models.email_config import EmailConfig
from app.models.task import Task
from app.services.calendar.router import list_events_range
from app.services.email.service import fetch_inbox, send_email

router = APIRouter()

ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
MODEL = "claude-haiku-4-5-20251001"   # más barato para resúmenes automáticos


async def _generate_summary(data: dict) -> str:
    """Pide a Claude que genere el resumen semanal en texto natural."""
    prompt = f"""Sos MATE, el asistente personal de Javier. 
Generá un resumen semanal ejecutivo en español, tono natural y directo, sin bullets.
Destacá lo más importante de cada sección.

DATOS DE LA SEMANA:
- Eventos del calendario: {data['events_count']} eventos. Títulos: {', '.join(data['event_titles'][:8]) or 'ninguno'}.
- Emails recibidos: {data['emails_count']}. Remitentes frecuentes: {', '.join(data['top_senders'][:5]) or 'ninguno'}.
- Tareas completadas esta semana: {data['tasks_completed']}.
- Tareas aún pendientes: {data['tasks_pending']}. Más urgentes: {', '.join(data['pending_titles'][:3]) or 'ninguna'}.

Empezá con "Acá va tu resumen de la semana, Javier." y terminá con una observación breve o motivación.
Máximo 200 palabras."""

    try:
        response = ANTHROPIC_CLIENT.messages.create(
            model=MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception:
        # Fallback: resumen simple sin Claude
        lines = [f"Resumen de la semana, Javier."]
        lines.append(f"Tuviste {data['events_count']} eventos en el calendario.")
        lines.append(f"Recibiste {data['emails_count']} emails.")
        lines.append(f"Completaste {data['tasks_completed']} tareas y tenés {data['tasks_pending']} pendientes.")
        if data['pending_titles']:
            lines.append(f"Las más urgentes: {', '.join(data['pending_titles'][:3])}.")
        return " ".join(lines)


@router.get("/briefing/weekly")
async def get_weekly_briefing(
    send_mail: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    data = {}

    # ── Calendario: últimos 7 días ─────────────────────────────────────────
    events = []
    try:
        result = await db.execute(
            select(CalendarConfig)
            .where(CalendarConfig.user_id == current_user.id)
            .where(CalendarConfig.enabled == True)
        )
        for cal_cfg in result.scalars().all():
            events.extend(await list_events_range(
                cal_cfg,
                time_min=week_ago.isoformat(),
                time_max=now.isoformat(),
                max_results=50,
            ))
        events.sort(key=lambda e: e.get("start") or "")
    except Exception:
        pass

    data["events_count"] = len(events)
    data["event_titles"] = [e.get("summary", "") for e in events]

    # ── Emails: inbox de la semana ─────────────────────────────────────────
    all_emails = []
    email_cfgs_result = await db.execute(
        select(EmailConfig)
        .where(EmailConfig.user_id == current_user.id)
        .where(EmailConfig.enabled == True)
    )
    email_cfgs = email_cfgs_result.scalars().all()

    first_cfg = email_cfgs[0] if email_cfgs else None

    for cfg in email_cfgs:
        try:
            inbox = await fetch_inbox(cfg, limit=30)
            all_emails.extend(inbox)
        except Exception:
            pass

    sender_counts: dict[str, int] = {}
    for m in all_emails:
        sender = m.get("from", "").split("<")[0].strip() or "desconocido"
        sender_counts[sender] = sender_counts.get(sender, 0) + 1
    top_senders = sorted(sender_counts, key=lambda k: sender_counts[k], reverse=True)

    data["emails_count"] = len(all_emails)
    data["top_senders"] = top_senders

    # ── Tareas ────────────────────────────────────────────────────────────
    completed_result = await db.execute(
        select(Task)
        .where(Task.user_id == current_user.id)
        .where(Task.completed == True)
        .where(Task.created_at >= week_ago.replace(tzinfo=None))
    )
    completed_tasks = completed_result.scalars().all()

    pending_result = await db.execute(
        select(Task)
        .where(Task.user_id == current_user.id)
        .where(Task.completed == False)
        .order_by(Task.due_date.asc().nullslast())
        .limit(10)
    )
    pending_tasks = pending_result.scalars().all()

    data["tasks_completed"] = len(completed_tasks)
    data["tasks_pending"] = len(pending_tasks)
    data["pending_titles"] = [t.title for t in pending_tasks[:5]]

    # ── Generar resumen con Claude ─────────────────────────────────────────
    summary_text = await _generate_summary(data)

    # ── Enviar por email ───────────────────────────────────────────────────
    sent = False
    if send_mail and first_cfg:
        subject = f"MATE — Resumen semanal {now.strftime('%d/%m/%Y')}"
        body = summary_text + f"\n\n---\nGenerado automáticamente por MATE el {now.strftime('%A %d de %B de %Y a las %H:%M')}."
        try:
            sent = await send_email(first_cfg, to=current_user.email, subject=subject, body=body)
        except Exception:
            pass

    return {
        "text": summary_text,
        "data": data,
        "email_sent": sent,
        "generated_at": now.isoformat(),
    }
