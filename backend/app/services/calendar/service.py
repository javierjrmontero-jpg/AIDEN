"""
Servicio de Google Calendar para MATE.

Usa OAuth2 con refresh_token persistido por usuario (tabla calendar_configs).
El client_id / client_secret de la app viven en .env (settings).
Las llamadas a la API de Google son síncronas, por eso se envuelven en
asyncio.to_thread para no bloquear el event loop de FastAPI.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_TZ = "America/Argentina/Buenos_Aires"  # UTC-3, válido para toda Argentina


# --------------------------------------------------------------------------- #
# Helpers síncronos (se ejecutan en thread aparte)
# --------------------------------------------------------------------------- #
def _credentials(refresh_token: str) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )


def _build_service(refresh_token: str):
    creds = _credentials(refresh_token)
    creds.refresh(Request())  # obtiene un access_token fresco
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _list_sync(refresh_token: str, calendar_id: str, max_results: int, days_ahead: int):
    service = _build_service(refresh_token)
    now = datetime.now(timezone.utc)
    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=days_ahead)).isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = []
    for ev in result.get("items", []):
        start = ev.get("start", {})
        end = ev.get("end", {})
        events.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary", "(sin título)"),
                "description": ev.get("description", ""),
                "location": ev.get("location", ""),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "all_day": "date" in start,
                "html_link": ev.get("htmlLink", ""),
            }
        )
    return events


def _create_sync(
    refresh_token: str,
    calendar_id: str,
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str,
    location: str,
    tz: str,
):
    service = _build_service(refresh_token)
    body = {"summary": summary}
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    # Evento de día completo si la fecha viene como YYYY-MM-DD (10 chars)
    if len(start_iso) == 10:
        body["start"] = {"date": start_iso}
        body["end"] = {"date": end_iso or start_iso}
    else:
        body["start"] = {"dateTime": start_iso, "timeZone": tz}
        body["end"] = {"dateTime": end_iso, "timeZone": tz}

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    cstart = created.get("start", {})
    return {
        "id": created.get("id"),
        "summary": created.get("summary"),
        "start": cstart.get("dateTime") or cstart.get("date"),
        "html_link": created.get("htmlLink", ""),
    }


def _account_email_sync(refresh_token: str) -> str:
    """Devuelve el email de la cuenta (id del calendario primario).
    Sirve además para validar que el refresh_token funciona."""
    service = _build_service(refresh_token)
    cal = service.calendars().get(calendarId="primary").execute()
    return cal.get("id", "")


# --------------------------------------------------------------------------- #
# API pública asíncrona
# --------------------------------------------------------------------------- #
async def list_upcoming_events(config, max_results: int = 10, days_ahead: int = 7):
    return await asyncio.to_thread(
        _list_sync, config.refresh_token, config.calendar_id or "primary", max_results, days_ahead
    )


async def create_event(
    config,
    summary: str,
    start_iso: str,
    end_iso: str = "",
    description: str = "",
    location: str = "",
    tz: str = DEFAULT_TZ,
):
    # Duración por defecto 1h si se pasó hora de inicio sin fin
    if not end_iso and len(start_iso) > 10:
        try:
            end_iso = (datetime.fromisoformat(start_iso) + timedelta(hours=1)).isoformat()
        except ValueError:
            end_iso = start_iso
    return await asyncio.to_thread(
        _create_sync,
        config.refresh_token,
        config.calendar_id or "primary",
        summary,
        start_iso,
        end_iso,
        description,
        location,
        tz,
    )


async def get_account_email(refresh_token: str) -> str:
    return await asyncio.to_thread(_account_email_sync, refresh_token)


def format_events_for_prompt(events: list) -> str:
    """Texto compacto de la agenda para inyectar en el system prompt del chat."""
    if not events:
        return "No hay eventos próximos o el calendario no está conectado."
    lines = [f"Tenés {len(events)} evento(s) próximo(s):"]
    for e in events:
        when = e["start"] or ""
        if e.get("all_day"):
            when += " (todo el día)"
        loc = f" @ {e['location']}" if e.get("location") else ""
        lines.append(f"- {when} · {e['summary']}{loc}")
    return "\n".join(lines)
