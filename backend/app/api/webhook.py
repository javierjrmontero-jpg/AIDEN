import logging
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import httpx
from app.core.config import settings
from app.core.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class TriggerRequest(BaseModel):
    workflow: str          # nombre del workflow / path del webhook en n8n
    payload: dict = {}


class N8nEvent(BaseModel):
    event: str
    data: Any = None
    source: Optional[str] = "n8n"


# Almacenamiento en memoria de los últimos eventos recibidos desde n8n
# En producción se puede persistir en DB o emitir por WebSocket.
_received_events: list[dict] = []
MAX_EVENTS = 100


@router.post("/webhook/trigger")
async def trigger_n8n(
    request: TriggerRequest,
    current_user: User = Depends(get_current_user),
):
    """MATE → n8n: dispara un webhook en n8n."""
    if not settings.N8N_WEBHOOK_URL:
        raise HTTPException(status_code=503, detail="N8N_WEBHOOK_URL no configurada")

    url = f"{settings.N8N_WEBHOOK_URL.rstrip('/')}/{request.workflow}"
    headers = {}
    if settings.N8N_API_KEY:
        headers["X-N8N-API-KEY"] = settings.N8N_API_KEY

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=request.payload, headers=headers)
            resp.raise_for_status()
            return {"status": "ok", "n8n_status": resp.status_code, "response": resp.json() if resp.content else {}}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"n8n respondió {e.response.status_code}: {e.response.text}")
    except Exception as e:
        logger.error(f"Error disparando webhook n8n: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/webhook/receive")
async def receive_from_n8n(
    event: N8nEvent,
    x_webhook_secret: Optional[str] = Header(None),
):
    """n8n → MATE: recibe un evento desde un workflow de n8n.

    Configurar en n8n: HTTP Request → POST https://mate.molmont.com.ar/api/v1/webhook/receive
    Header requerido: X-Webhook-Secret: <WEBHOOK_SECRET del .env>
    """
    if settings.WEBHOOK_SECRET and x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Webhook secret inválido")
    entry = {"event": event.event, "data": event.data, "source": event.source}
    _received_events.append(entry)
    if len(_received_events) > MAX_EVENTS:
        _received_events.pop(0)

    logger.info(f"Evento recibido de n8n: {event.event}")
    return {"status": "received", "event": event.event}


@router.get("/webhook/events")
async def list_events(current_user: User = Depends(get_current_user)):
    """Devuelve los últimos eventos recibidos desde n8n."""
    return {"events": list(reversed(_received_events))}
