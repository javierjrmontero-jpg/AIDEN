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
# Normalización de fechas
# --------------------------------------------------------------------------- #
def _is_all_day(value: str) -> bool:
    """True si el valor es solo fecha (YYYY-MM-DD), sin hora."""
    return len(value.strip()) == 10 and value.count("-") == 2 and "T" not in value


def _normalize_datetime(value: str) -> str:
    """
    Convierte la entrada a RFC3339 que Google acepta.
    - 'YYYY-MM-DD'              -> evento de día completo (se devuelve igual)
    - 'YYYY-MM-DDTHH:MM'        -> agrega ':00' segundos
    - 'YYYY-MM-DDTHH:MM:SS'     -> se deja igual
    El input datetime-local del navegador no manda segundos, de ahí el ajuste.
    """
    value = value.strip()
    if _is_all_day(value):
        return value
    # Reemplaza espacio por 'T' por si viene 'YYYY-MM-DD HH:MM'
    value = value.replace(" ", "T")
    # Si tiene formato YYYY-MM-DDTHH:MM (16 chars) -> faltan los segundos
    if len(value) == 16:
        value = value + ":00"
    return value


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

    if _is_all_day(start_iso):
        # Evento de día completo. El 'end.date' en Google es EXCLUSIVO:
        # para un evento de un día, end = start + 1 día.
        end_date = end_iso if (end_iso and _is_all_day(end_iso)) else None
        if not end_date:
            d = datetime.strptime(start_iso, "%Y-%m-%d") + timedelta(days=1)
            end_date = d.strftime("%Y-%m-%d")
        body["start"] = {"date": start_iso}
        body["end"] = {"date": end_date}
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


def _list_range_sync(refresh_token: str, calendar_id: str, time_min: str, time_max: str, max_results: int):
    service = _build_service(refresh_token)
    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
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
        events.append({
            "id": ev.get("id"),
            "summary": ev.get("summary", "(sin título)"),
            "start": start.get("dateTime") or start.get("date"),
            "end": end.get("dateTime") or end.get("date"),
            "all_day": "date" in start,
        })
    return events


async def list_events_range(config, time_min: str, time_max: str, max_results: int = 50):
    """Eventos entre dos timestamps ISO 8601 (pasado o futuro)."""
    return await asyncio.to_thread(
        _list_range_sync,
        config.refresh_token,
        config.calendar_id or "primary",
        time_min,
        time_max,
        max_results,
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
    # Normaliza fechas (agrega segundos si faltan, etc.)
    start_norm = _normalize_datetime(start_iso)
    end_norm = _normalize_datetime(end_iso) if end_iso else ""

    # Si hay hora de inicio pero no de fin -> +1h por defecto
    if not end_norm and not _is_all_day(start_norm):
        try:
            end_norm = (datetime.fromisoformat(start_norm) + timedelta(hours=1)).isoformat()
        except ValueError:
            end_norm = start_norm

    return await asyncio.to_thread(
        _create_sync,
        config.refresh_token,
        config.calendar_id or "primary",
        summary,
        start_norm,
        end_norm,
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
