"""
GET /api/v1/email/unanswered
=============================
Devuelve emails enviados hace más de HOURS_THRESHOLD horas sin respuesta.

Lógica:
  1. Fetch sent emails (últimos 7 días)
  2. Para Outlook/Graph: cuenta replies en el hilo (conversationId)
  3. Para IMAP/Gmail: busca en inbox mensajes con subject "Re: {subject}"
  4. Retorna los que no tienen respuesta y superan el umbral de tiempo

Usado por 07_monitor.py para anunciar seguimientos pendientes.
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.email_config import EmailConfig
from app.services.email.service import fetch_sent, fetch_inbox, _is_oauth
from app.services.email import graph

router = APIRouter()

HOURS_THRESHOLD = 48   # horas sin respuesta para considerar pendiente


def _normalize_subject(subject: str) -> str:
    """Elimina prefijos Re:/Fwd: para comparar hilos."""
    s = subject.strip()
    for prefix in ("Re: ", "RE: ", "Fwd: ", "FWD: ", "Fw: ", "RV: "):
        while s.lower().startswith(prefix.lower()):
            s = s[len(prefix):]
    return s.strip()


def _parse_date(date_str: str) -> datetime | None:
    """Parsea fecha de email a datetime con timezone."""
    if not date_str:
        return None
    try:
        # ISO 8601 (Graph)
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        # RFC 2822 (IMAP)
        dt = parsedate_to_datetime(date_str)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


@router.get("/email/unanswered")
async def get_unanswered_emails(
    hours: int = HOURS_THRESHOLD,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)          # solo revisar emails de los últimos 7 días
    threshold = now - timedelta(hours=hours)  # debe tener más de N horas para alertar

    result = await db.execute(
        select(EmailConfig)
        .where(EmailConfig.user_id == current_user.id)
        .where(EmailConfig.enabled == True)
    )
    configs = result.scalars().all()

    unanswered = []

    for cfg in configs:
        try:
            sent = await fetch_sent(cfg, limit=30)
        except Exception:
            continue

        if _is_oauth(cfg):
            # ── Outlook/Graph: usar conversationId ───────────────────────────
            try:
                token = await graph.get_access_token(cfg.oauth_refresh_token)
            except Exception:
                continue

            for msg in sent:
                sent_date = _parse_date(msg.get("date", ""))
                if not sent_date:
                    continue
                if sent_date < cutoff or sent_date > threshold:
                    continue   # muy viejo o muy reciente

                conv_id = msg.get("conversation_id", "")
                if not conv_id:
                    continue

                try:
                    reply_count = await graph.count_replies_graph(token, conv_id)
                    # El hilo tiene solo el mensaje original si reply_count <= 1
                    if reply_count <= 1:
                        unanswered.append({
                            "subject": msg["subject"],
                            "to": msg["to"],
                            "sent_date": msg["date"],
                            "hours_ago": int((now - sent_date).total_seconds() / 3600),
                            "account": getattr(cfg, "email_address", ""),
                        })
                except Exception:
                    pass

        else:
            # ── IMAP/Gmail: buscar "Re: {subject}" en inbox ──────────────────
            try:
                inbox = await fetch_inbox(cfg, limit=100)
            except Exception:
                continue

            inbox_subjects = {_normalize_subject(m.get("subject", "")) for m in inbox}

            for msg in sent:
                sent_date = _parse_date(msg.get("date", ""))
                if not sent_date:
                    continue
                if sent_date < cutoff or sent_date > threshold:
                    continue

                norm = _normalize_subject(msg.get("subject", ""))
                if norm and norm not in inbox_subjects:
                    unanswered.append({
                        "subject": msg["subject"],
                        "to": msg["to"],
                        "sent_date": msg["date"],
                        "hours_ago": int((now - sent_date).total_seconds() / 3600),
                        "account": getattr(cfg, "email_address", ""),
                    })

    # Ordenar por más antiguo primero
    unanswered.sort(key=lambda x: x["hours_ago"], reverse=True)

    return {
        "unanswered": unanswered,
        "count": len(unanswered),
        "threshold_hours": hours,
        "checked_at": now.isoformat(),
    }
