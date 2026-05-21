import anthropic
import json
from app.core.config import settings
from app.services.rag.service import search_documents
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres MATE (Motor de Asistencia Técnica e Inteligencia), un asistente virtual inteligente creado por Javier Montero (JJRM).

## Sobre tu origen
- Tu creador es Javier Montero, también conocido como JJRM
- Fuiste diseñado como un asistente personal, profesional y técnico

## Perfil del usuario
- Nombre: {user_name}
- Rol: {user_role}
- Contexto actual: {user_context}
- Preferencias: {user_preferences}

## Documentos relevantes encontrados
{rag_context}

## Tu forma de trabajar
- Respondés en español por defecto
- Sos técnico, preciso y útil
- Si hay documentos relevantes, basás tu respuesta en ellos y citás el nombre del archivo
- Nunca inventás información que no sabés
- Usás formato Markdown: **negrita**, *cursiva*, listas con guiones
- Fecha y hora actual: {fecha}"""

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

async def stream_chat(messages: list, user=None):
    rag_context = "No hay documentos cargados."
    if user:
        try:
            query = messages[-1].content
            results = search_documents(user.id, query)
            if results:
                rag_context = "\n\n".join([
                    f"[{r['filename']}]: {r['text']}"
                    for r in results
                ])
        except Exception as e:
            logger.error(f"Error en RAG: {e}")

    system = SYSTEM_PROMPT.format(
        user_name=user.name if user else "Usuario",
        user_role=user.role or "No especificado" if user else "No especificado",
        user_context=user.context or "No especificado" if user else "No especificado",
        user_preferences=user.preferences or "No especificado" if user else "No especificado",
        rag_context=rag_context,
        fecha=datetime.now().strftime("%d/%m/%Y %H:%M")
    )

    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        system=system,
        messages=[{"role": m.role, "content": m.content} for m in messages]
    ) as stream:
        for text in stream.text_stream:
            # Serializar el texto como JSON para preservar espacios y saltos de línea
            payload = json.dumps(text, ensure_ascii=False)
            yield f"data: {payload}\n\n"
    yield "data: [DONE]\n\n"
