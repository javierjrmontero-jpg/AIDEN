"""
MATE — Chequeo de salud de tokens OAuth (Google Calendar / Microsoft Graph)
===========================================================================
Recorre las cuentas configuradas (calendar_configs, email_configs con
auth_type='oauth') e intenta refrescar cada refresh_token contra el
proveedor correspondiente.

Por qué esto reemplaza a "vigilar una fecha de vencimiento":
  - Google (producción): el refresh token NO expira por tiempo, pero se
    invalida tras 6 meses sin uso, cambio de contraseña o revocación.
  - Microsoft (cuenta personal): el refresh token tiene una ventana
    deslizante de ~90 días de INACTIVIDAD — cada refresh exitoso la
    reinicia. Correr este script periódicamente no solo detecta un token
    roto: para Microsoft, además LO MANTIENE VIVO aunque el usuario no
    use el email/calendario esa semana.

Uso (dentro del contenedor backend, mismo entorno que la app):
    docker compose exec backend python3 scripts/check_oauth_health.py

Código de salida: 0 si todo OK, 1 si algún token falló (útil para cron +
notificación, p. ej. encadenar `|| mail -s "MATE: token OAuth roto" ...`).
"""

import asyncio
import sys

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.email_config import EmailConfig
from app.models.calendar_config import CalendarConfig
from app.services.email.graph import get_access_token as graph_get_access_token
from app.services.email.graph import get_profile_email as graph_get_profile_email

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def check_google(refresh_token: str) -> tuple[bool, str]:
    """Intenta canjear el refresh_token de Google por un access_token."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        data = resp.json()
        if "access_token" in data:
            return True, "token vigente — refresh OK"
        return False, data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


async def check_microsoft(refresh_token: str) -> tuple[bool, str]:
    """Intenta canjear el refresh_token de Microsoft Graph y valida el perfil."""
    try:
        access_token = await graph_get_access_token(refresh_token)
        email = await graph_get_profile_email(access_token)
        return True, f"token vigente — refresh OK (perfil: {email or 'sin email'})"
    except Exception as e:
        return False, str(e)


async def main() -> int:
    engine = create_async_engine(settings.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://"))
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    failures = 0
    checked = 0

    async with Session() as session:
        # ── Calendario (Google) ──────────────────────────────────────────
        result = await session.execute(
            select(CalendarConfig).where(CalendarConfig.enabled.is_(True))
        )
        for cfg in result.scalars().all():
            checked += 1
            label = f"[Calendar/{cfg.provider}] {cfg.google_email or cfg.id}"
            if cfg.provider == "google":
                ok, detail = await check_google(cfg.refresh_token)
            else:
                ok, detail = False, f"proveedor '{cfg.provider}' no soportado por este chequeo"
            _report(label, ok, detail)
            if not ok:
                failures += 1

        # ── Email OAuth (Microsoft Graph) ────────────────────────────────
        result = await session.execute(
            select(EmailConfig).where(
                EmailConfig.enabled.is_(True),
                EmailConfig.auth_type == "oauth",
            )
        )
        for cfg in result.scalars().all():
            checked += 1
            label = f"[Email/{cfg.provider}] {cfg.email_address or cfg.id}"
            if not cfg.oauth_refresh_token:
                _report(label, False, "auth_type='oauth' pero sin oauth_refresh_token guardado")
                failures += 1
                continue
            ok, detail = await check_microsoft(cfg.oauth_refresh_token)
            _report(label, ok, detail)
            if not ok:
                failures += 1

    await engine.dispose()

    print(f"\n— Resumen: {checked} cuenta(s) verificada(s), {failures} con problema(s) —")
    if failures:
        print("⚠️  Acción requerida: reconectar la(s) cuenta(s) marcada(s) con ❌")
        print("    Google   → repetir 'python scripts/google_calendar_auth.py' y pegar el nuevo refresh token en /calendar")
        print("    Outlook  → repetir 'python scripts/microsoft_email_auth.py' y pegar el nuevo refresh token en /email")
    return 1 if failures else 0


def _report(label: str, ok: bool, detail: str) -> None:
    icon = "✅" if ok else "❌"
    print(f"{icon} {label}: {detail}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))