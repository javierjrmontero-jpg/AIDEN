"""
Cliente de Microsoft Graph para email (Outlook/Hotmail personal).

Se usa para cuentas con auth_type='oauth'. Obtiene un access_token a partir
del refresh_token guardado y opera sobre /me/messages y /me/sendMail.

Graph NO depende de que IMAP/SMTP estén habilitados en la cuenta, por eso es
robusto para cuentas consumer donde Microsoft deshabilita SMTP AUTH.
"""

import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "offline_access User.Read Mail.Read Mail.Send"


async def get_access_token(refresh_token: str) -> str:
    """Canjea el refresh_token por un access_token fresco."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": SCOPE,
            },
        )
    data = resp.json()
    if "access_token" not in data:
        raise Exception(data.get("error_description", "No se pudo refrescar el token"))
    return data["access_token"]


def _map_message(m: dict) -> dict:
    """Normaliza un mensaje de Graph al formato que usa MATE."""
    sender = ""
    frm = m.get("from") or m.get("sender") or {}
    if isinstance(frm, dict):
        sender = frm.get("emailAddress", {}).get("address", "")
    return {
        "id": m.get("id", ""),
        "subject": m.get("subject", "") or "(sin asunto)",
        "from": sender,
        "date": m.get("receivedDateTime", ""),
        "body": (m.get("bodyPreview", "") or "")[:3000],
        "read": m.get("isRead", False),
    }


async def fetch_inbox_graph(access_token: str, limit: int = 10) -> list:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "$top": limit,
        "$select": "subject,from,receivedDateTime,bodyPreview,isRead",
        "$orderby": "receivedDateTime desc",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{GRAPH}/me/messages", headers=headers, params=params)
    if resp.status_code != 200:
        raise Exception(f"Graph error {resp.status_code}: {resp.text[:200]}")
    return [_map_message(m) for m in resp.json().get("value", [])]


async def fetch_unread_graph(access_token: str, limit: int = 10) -> list:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "$filter": "isRead eq false",
        "$top": limit,
        "$select": "subject,from,receivedDateTime,bodyPreview,isRead",
        "$orderby": "receivedDateTime desc",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GRAPH}/me/mailFolders/Inbox/messages", headers=headers, params=params
        )
    if resp.status_code != 200:
        raise Exception(f"Graph error {resp.status_code}: {resp.text[:200]}")
    return [_map_message(m) for m in resp.json().get("value", [])]


async def send_mail_graph(access_token: str, to: str, subject: str, body: str) -> bool:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": True,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{GRAPH}/me/sendMail", headers=headers, json=payload)
    if resp.status_code not in (200, 202):
        raise Exception(f"Graph error {resp.status_code}: {resp.text[:200]}")
    return True


async def get_profile_email(access_token: str) -> str:
    """Devuelve el email de la cuenta. Valida que el token funciona."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{GRAPH}/me?$select=mail,userPrincipalName", headers=headers)
    data = resp.json()
    return data.get("mail") or data.get("userPrincipalName") or ""
