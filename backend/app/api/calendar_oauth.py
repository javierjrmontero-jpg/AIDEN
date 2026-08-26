"""
Conexión de calendarios desde la propia interfaz de MATE.

Sin esto, dar de alta una agenda exige correr un script con el client_secret
de la aplicación en la máquina del usuario: inviable para cualquiera que no
sea el administrador, y además reparte un secreto que no debe salir del
servidor.

El redirect de OAuth no puede llevar el header Authorization, así que la
identidad del usuario viaja firmada dentro del parámetro `state`.
"""

import hashlib
import hmac
import logging
import secrets
import time
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.models.calendar_config import CalendarConfig
from app.models.user import User
from app.services.calendar.service import get_account_email

router = APIRouter()
logger = logging.getLogger(__name__)

_BASE = "https://mate.molmont.com.ar"
_FRONT = f"{_BASE}/calendar"
_STATE_TTL = 600

_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_REDIRECT = f"{_BASE}/api/v1/calendar/connect/google/callback"
_GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar openid email"


def _make_state(user_id: str) -> str:
    nonce = secrets.token_urlsafe(12)
    ts = str(int(time.time()))
    msg = f"{nonce}:{user_id}:{ts}"
    sig = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}:{sig}"


def _read_state(state: str) -> str | None:
    """Devuelve el user_id, o None si la firma no valida o expiró."""
    try:
        nonce, user_id, ts, sig = state.rsplit(":", 3)
        msg = f"{nonce}:{user_id}:{ts}"
        expected = hmac.new(settings.SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if time.time() - int(ts) > _STATE_TTL:
            return None
        return user_id
    except Exception:
        return None


def _cerrar(mensaje: str, ok: bool = True) -> HTMLResponse:
    """Cierra la ventana de OAuth y avisa al calendario que se actualice."""
    color = "#58C08E" if ok else "#E5544B"
    return HTMLResponse(
        "<html><head><meta charset='utf-8'></head>"
        "<body style='background:#0b0f14;color:#c6d3de;font-family:system-ui;"
        "display:grid;place-items:center;height:100vh;margin:0'>"
        f"<div style='text-align:center'><p style='color:{color};font-size:16px'>{mensaje}</p>"
        "<p style='color:#6e8090;font-size:13px'>Podés cerrar esta ventana.</p></div>"
        "<script>try{window.opener&&window.opener.postMessage('calendar-connected','*')}catch(e){}"
        f"setTimeout(function(){{window.close();window.location.replace('{_FRONT}')}},1800);</script>"
        "</body></html>"
    )


@router.get("/calendar/connect/google")
async def google_connect_url(current_user: User = Depends(get_current_user)):
    """Devuelve la URL de autorización. El frontend la abre en otra ventana."""
    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _GOOGLE_REDIRECT,
        "response_type": "code",
        "scope": _GOOGLE_SCOPE,
        "state": _make_state(current_user.id),
        "access_type": "offline",
        # Sin esto Google no reemite refresh_token a una cuenta que ya autorizó.
        "prompt": "consent",
    })
    return {"url": f"{_GOOGLE_AUTH}?{params}"}


@router.get("/calendar/connect/google/callback", response_class=HTMLResponse)
async def google_connect_callback(code: str = None, state: str = None, error: str = None):
    if error or not code:
        return _cerrar("Autorización cancelada.", ok=False)

    user_id = _read_state(state or "")
    if not user_id:
        logger.warning("Calendario: state inválido o expirado")
        return _cerrar("El enlace expiró. Volvé a intentarlo.", ok=False)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(_GOOGLE_TOKEN, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": _GOOGLE_REDIRECT,
            "grant_type": "authorization_code",
        })
    if resp.status_code != 200:
        logger.error(f"Calendario: canje de código falló — {resp.text}")
        return _cerrar("Google rechazó la autorización.", ok=False)

    refresh_token = resp.json().get("refresh_token")
    if not refresh_token:
        # Pasa si la cuenta ya autorizó y Google no reemitió el token.
        return _cerrar(
            "Google no devolvió un token de actualización. "
            "Revocá el acceso a MATE en tu cuenta y probá de nuevo.", ok=False
        )

    try:
        email = await get_account_email(refresh_token, "web")
    except Exception as ex:
        logger.error(f"Calendario: el token no sirve para leer el calendario — {ex}")
        return _cerrar("No se pudo leer el calendario con esa cuenta.", ok=False)

    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(CalendarConfig)
            .where(CalendarConfig.user_id == user_id)
            .where(CalendarConfig.google_email == email)
        )
        existente = row.scalar_one_or_none()
        if existente:
            existente.refresh_token = refresh_token
            existente.client_kind = "web"
            existente.enabled = True
        else:
            db.add(CalendarConfig(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider="google",
                google_email=email,
                refresh_token=refresh_token,
                client_kind="web",
                calendar_id="primary",
            ))
        await db.commit()

    logger.info(f"Calendario conectado para {email}")
    return _cerrar(f"Calendario de {email} conectado.")
