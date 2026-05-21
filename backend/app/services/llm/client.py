import anthropic
import json
import logging
from app.core.config import settings
from app.services.rag.service import search_documents
from app.services.search.service import web_search, format_results_for_llm
from datetime import datetime

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

## Documentos del usuario (RAG)
{rag_context}

## Resultados de búsqueda web
{web_context}

## Tu forma de trabajar
- Respondés en español por defecto
- Sos técnico, preciso y útil
- Si hay documentos relevantes, los usás y citás el archivo
- Si hay resultados web, los usás e indicás la fuente con la URL
- Si no hay información suficiente, lo decís claramente
- Nunca inventás información que no tenés
- Usás formato Markdown: **negrita**, *cursiva*, listas, tablas, código
- Fecha y hora actual: {fecha}"""

SEARCH_TRIGGER_WORDS = [
    "hoy", "ahora", "actual", "actualmente", "último", "últimos", "última", "últimas",
    "reciente", "recientes", "noticia", "noticias", "precio", "precios", "cotización",
    "novedad", "novedades", "resultado", "resultados", "partido", "clima", "tiempo",
    "cuando", "cuándo", "quién ganó", "qué pasó", "este año", "este mes",
    "2024", "2025", "2026", "lanzamiento", "nueva versión", "update", "release"
]

def should_search_web(query: str) -> bool:
    if not settings.BRAVE_SEARCH_API_KEY or not settings.SEARCH_ENABLED:
        return False
    query_lower = query.lower()
    return any(word in query_lower for word in SEARCH_TRIGGER_WORDS)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

async def stream_chat(messages: list, user=None):
    query = messages[-1].content

    # RAG sobre documentos del usuario
    rag_context = "No hay documentos cargados."
    try:
        if user:
            results = search_documents(user.id, query)
            if results:
                rag_context = "\n\n".join([
                    f"[{r['filename']}]: {r['text']}"
                    for r in results
                ])
    except Exception as e:
        logger.error(f"Error en RAG: {e}")

    # Búsqueda web si es necesario
    web_context = "No se realizó búsqueda web."
    try:
        if should_search_web(query):
            logger.info(f"Activando búsqueda web para: '{query}'")
            web_results = await web_search(query)
            if web_results:
                web_context = format_results_for_llm(web_results)
                logger.info(f"Búsqueda web completada: {len(web_results)} resultados")
    except Exception as e:
        logger.error(f"Error en búsqueda web: {e}")

    system = SYSTEM_PROMPT.format(
        user_name=user.name if user else "Usuario",
        user_role=user.role or "No especificado" if user else "No especificado",
        user_context=user.context or "No especificado" if user else "No especificado",
        user_preferences=user.preferences or "No especificado" if user else "No especificado",
        rag_context=rag_context,
        web_context=web_context,
        fecha=datetime.now().strftime("%d/%m/%Y %H:%M")
    )

    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        system=system,
        messages=[{"role": m.role, "content": m.content} for m in messages]
    ) as stream:
        for text in stream.text_stream:
            payload = json.dumps(text, ensure_ascii=False)
            yield f"data: {payload}\n\n"
    yield "data: [DONE]\n\n"
