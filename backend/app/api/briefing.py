"""
GET /api/v1/briefing — Resumen del día para TTS
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.calendar_config import CalendarConfig
from app.models.email_config import EmailConfig
from app.models.task import Task
from app.services.calendar.router import list_upcoming_events
from app.services.email.service import fetch_unread

router = APIRouter()

def _format_time(iso: str) -> str:
    try:
        if "T" in iso:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%-H:%M")
        return iso
    except Exception:
        return iso

@router.get("/briefing")
async def get_briefing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now()
    sections: dict = {}
    lines: list[str] = [
        f"Buenos días, Javier. Hoy es {now.strftime('%A %d de %B de %Y')}. "
        f"Acá va tu resumen del día."
    ]

    # ── Calendario ────────────────────────────────────────────────────────────
    try:
        result = await db.execute(
            select(CalendarConfig)
            .where(CalendarConfig.user_id == current_user.id)
            .where(CalendarConfig.enabled == True)
        )
        cal_cfg = result.scalar_one_or_none()
        if cal_cfg:
            events = await list_upcoming_events(cal_cfg, max_results=10, days_ahead=2)
            today_str = now.strftime("%Y-%m-%d")
            tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            today_events = [e for e in events if e.get("start", "").startswith(today_str)]
            tomorrow_events = [e for e in events if e.get("start", "").startswith(tomorrow_str)]
            if today_events:
                lines.append(f"Hoy tenés {len(today_events)} evento{'s' if len(today_events)>1 else ''}:")
                for ev in today_events:
                    lines.append(f"  — {ev.get('summary','Sin título')} a las {_format_time(ev.get('start',''))}.")
            else:
                lines.append("No tenés eventos en el calendario para hoy.")
            if tomorrow_events:
                lines.append(f"Mañana: {len(tomorrow_events)} evento{'s' if len(tomorrow_events)>1 else ''} programado{'s' if len(tomorrow_events)>1 else ''}.")
            sections["calendar"] = {
                "today": [{"summary": e.get("summary"), "start": e.get("start")} for e in today_events],
                "tomorrow": [{"summary": e.get("summary"), "start": e.get("start")} for e in tomorrow_events],
            }
        else:
            lines.append("No hay calendario conectado.")
            sections["calendar"] = None
    except Exception as ex:
        lines.append("No pude acceder al calendario.")
        sections["calendar"] = {"error": str(ex)}

    # ── Emails no leídos ──────────────────────────────────────────────────────
    try:
        result = await db.execute(
            select(EmailConfig)
            .where(EmailConfig.user_id == current_user.id)
            .where(EmailConfig.enabled == True)
        )
        email_cfgs = result.scalars().all()
        all_unread = []
        for cfg in email_cfgs:
            try:
                unread = await fetch_unread(cfg, limit=10)
                for m in unread:
                    m["account"] = getattr(cfg, "email_address", "")
                all_unread.extend(unread)
            except Exception:
                pass
        if all_unread:
            lines.append(
                f"Tenés {len(all_unread)} email{'s' if len(all_unread)>1 else ''} no leído{'s' if len(all_unread)>1 else ''}. "
                f"Los primeros remitentes: "
                + ", ".join(m.get("from","desconocido").split("<")[0].strip() for m in all_unread[:3]) + "."
            )
        else:
            lines.append("No tenés emails no leídos.")
        sections["email"] = {"unread_count": len(all_unread), "senders": [m.get("from","") for m in all_unread[:5]]}
    except Exception as ex:
        lines.append("No pude revisar el email.")
        sections["email"] = {"error": str(ex)}

    # ── Tareas pendientes ─────────────────────────────────────────────────────
    try:
        result = await db.execute(
            select(Task)
            .where(Task.user_id == current_user.id)
            .where(Task.completed == False)
            .order_by(Task.due_date.asc().nullslast())
            .limit(5)
        )
        pending = result.scalars().all()
        if pending:
            high = [t for t in pending if t.priority == "high"]
            if high:
                lines.append(f"Tenés {len(high)} tarea{'s' if len(high)>1 else ''} de alta prioridad: " + ", ".join(t.title for t in high[:3]) + ".")
            else:
                lines.append(f"Tenés {len(pending)} tarea{'s' if len(pending)>1 else ''} pendiente{'s' if len(pending)>1 else ''}: " + ", ".join(t.title for t in pending[:3]) + ".")
        else:
            lines.append("No tenés tareas pendientes. ¡Bien!")
        sections["tasks"] = {"pending_count": len(pending), "items": [{"title": t.title, "priority": t.priority} for t in pending]}
    except Exception as ex:
        lines.append("No pude acceder a las tareas.")
        sections["tasks"] = {"error": str(ex)}

    lines.append("Eso es todo por ahora. ¿En qué empezamos?")
    return {"text": " ".join(lines), "sections": sections, "generated_at": now.isoformat()}
