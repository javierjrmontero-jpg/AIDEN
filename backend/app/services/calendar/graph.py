"""
Calendario de Outlook / Microsoft 365 vía Microsoft Graph.

A diferencia del proveedor de Google, que usa la librería oficial y llamadas
bloqueantes envueltas en threads, acá alcanza con HTTP: Graph es una API REST
plana y httpx ya es asíncrono, así que no hace falta salir del event loop.

Devuelve eventos con la misma forma que el proveedor de Google, para que la
capa de arriba no tenga que saber de dónde vienen.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_GRAPH = "https://graph.microsoft.com/v1.0"

# offline_access es lo que hace que Microsoft devuelva refresh_token.
SCOPES = "offline_access Calendars.ReadWrite User.Read"

DEFAULT_TZ = "America/Argentina/Buenos_Aires"


class GraphError(RuntimeError):
    pass


async def _access_token(refresh_token: str) -> str:
    """Canjea el refresh_token por un access_token de vida corta."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(_TOKEN_URL, data={
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": SCOPES,
        })
    if resp.status_code != 200:
        raise GraphError(f"No se pudo renovar el acceso a Microsoft: {resp.text[:200]}")
    token = resp.json().get("access_token")
    if not token:
        raise GraphError("Microsoft no devolvió access_token")
    return token


async def _get(refresh_token: str, ruta: str, params: dict | None = None) -> dict:
    token = await _access_token(refresh_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_GRAPH}{ruta}",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                # Sin esto Graph devuelve los horarios en UTC.
                "Prefer": f'outlook.timezone="{DEFAULT_TZ}"',
            },
        )
    if resp.status_code != 200:
        raise GraphError(f"Graph respondió {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def _normalizar(ev: dict) -> dict:
    """Traduce un evento de Graph a la forma que ya usa el resto de MATE."""
    inicio = ev.get("start", {}).get("dateTime", "")
    fin = ev.get("end", {}).get("dateTime", "")
    todo_el_dia = bool(ev.get("isAllDay"))
    return {
        "id": ev.get("id"),
        "summary": ev.get("subject") or "(sin título)",
        "description": (ev.get("bodyPreview") or "").strip(),
        "location": (ev.get("location") or {}).get("displayName", ""),
        # Graph devuelve microsegundos y sin zona; recortamos para que el
        # frontend lo parsee igual que los de Google.
        "start": inicio[:19] if not todo_el_dia else inicio[:10],
        "end": fin[:19] if not todo_el_dia else fin[:10],
        "all_day": todo_el_dia,
        "html_link": ev.get("webLink", ""),
    }


async def get_account_email(refresh_token: str) -> str:
    """Email de la cuenta. Sirve además para validar el refresh_token."""
    data = await _get(refresh_token, "/me")
    return data.get("mail") or data.get("userPrincipalName") or ""


async def list_upcoming_events(config, max_results: int = 10, days_ahead: int = 7):
    ahora = datetime.now(timezone.utc)
    data = await _get(
        config.refresh_token,
        "/me/calendarView",
        {
            "startDateTime": ahora.isoformat(),
            "endDateTime": (ahora + timedelta(days=days_ahead)).isoformat(),
            "$orderby": "start/dateTime",
            "$top": max_results,
            "$select": "id,subject,bodyPreview,location,start,end,isAllDay,webLink",
        },
    )
    return [_normalizar(e) for e in data.get("value", [])]


async def list_events_range(config, time_min: str, time_max: str, max_results: int = 50):
    data = await _get(
        config.refresh_token,
        "/me/calendarView",
        {
            "startDateTime": time_min,
            "endDateTime": time_max,
            "$orderby": "start/dateTime",
            "$top": max_results,
            "$select": "id,subject,start,end,isAllDay",
        },
    )
    return [_normalizar(e) for e in data.get("value", [])]


async def create_event(
    config,
    summary: str,
    start_iso: str,
    end_iso: str = "",
    description: str = "",
    location: str = "",
    tz: str = DEFAULT_TZ,
):
    todo_el_dia = len(start_iso.strip()) == 10

    if todo_el_dia:
        fin = end_iso if len(end_iso.strip()) == 10 else None
        if not fin:
            # En Graph, igual que en Google, el fin de un evento de día
            # completo es exclusivo.
            fin = (datetime.strptime(start_iso, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        inicio_dt, fin_dt = start_iso, fin
    else:
        inicio_dt = start_iso.replace(" ", "T")
        if len(inicio_dt) == 16:
            inicio_dt += ":00"
        fin_dt = (end_iso or "").replace(" ", "T")
        if len(fin_dt) == 16:
            fin_dt += ":00"
        if not fin_dt:
            fin_dt = (datetime.fromisoformat(inicio_dt) + timedelta(hours=1)).isoformat()

    cuerpo = {
        "subject": summary,
        "isAllDay": todo_el_dia,
        "start": {"dateTime": inicio_dt, "timeZone": tz},
        "end": {"dateTime": fin_dt, "timeZone": tz},
    }
    if description:
        cuerpo["body"] = {"contentType": "text", "content": description}
    if location:
        cuerpo["location"] = {"displayName": location}

    token = await _access_token(config.refresh_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_GRAPH}/me/events",
            json=cuerpo,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if resp.status_code not in (200, 201):
        raise GraphError(f"No se pudo crear el evento: {resp.text[:200]}")

    creado = resp.json()
    return {
        "id": creado.get("id"),
        "summary": creado.get("subject"),
        "start": creado.get("start", {}).get("dateTime", "")[:19],
        "html_link": creado.get("webLink", ""),
    }
