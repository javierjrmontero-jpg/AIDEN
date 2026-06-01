import anthropic
import json
import logging
from app.core.config import settings
from app.services.rag.service import search_documents
from app.services.search.service import web_search, format_results_for_llm
from datetime import datetime

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "es": "español",
    "en": "inglés",
    "pt": "portugués",
    "fr": "francés",
    "de": "alemán",
    "it": "italiano"
}

SYSTEM_PROMPT = """Eres MATE (Motor de Asistencia Técnica e Inteligencia), un asistente virtual inteligente by JJRM.

## Sobre tu origen
- Tu creador es Javier Montero, también conocido como JJRM
- Fuiste diseñado como un asistente personal, profesional y técnico

## Perfil del usuario
- Nombre: {user_name}
- Rol: {user_role}
- Contexto actual: {user_context}
- Preferencias: {user_preferences}
- Idioma preferido: {user_language}

## Lo que recordás del usuario (memorias previas)
{memories}

## Tareas pendientes del usuario
{tasks_context}

## Emails no leídos
{emails_context}

## Próximos eventos de tu calendario
{calendar_context}

## Documentos del usuario (RAG)
{rag_context}

## Resultados de búsqueda web
{web_context}

## Tu forma de trabajar
- Respondés SIEMPRE en {user_language} sin excepción, independientemente del idioma en que te escriban
- Si el usuario escribe en otro idioma, igual respondés en {user_language}
- Sos técnico, preciso y útil
- Usás las memorias previas para personalizar respuestas
- Si hay documentos relevantes, los usás y citás el archivo
- Si hay resultados web, los usás e indicás la fuente con la URL
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

async def stream_chat(messages: list, user=None, db=None):
    query = messages[-1].content

    # Memorias del usuario
    memories_text = "No hay memorias previas."
    if user and db:
        try:
            from app.services.memory.service import format_memories_for_prompt
            memories_text = await format_memories_for_prompt(db, user.id)
        except Exception as e:
            logger.error(f"Error cargando memorias: {e}")

    # Tareas pendientes
    tasks_text = "No hay tareas pendientes."
    if user and db:
        try:
            from sqlalchemy import select
            from app.models.task import Task
            result = await db.execute(
                select(Task)
                .where(Task.user_id == user.id)
                .where(Task.completed == False)
                .order_by(Task.due_date.asc())
                .limit(5)
            )
            pending_tasks = result.scalars().all()
            if pending_tasks:
                lines = []
                for t in pending_tasks:
                    due = f" (vence: {t.due_date.strftime('%d/%m/%Y')})" if t.due_date else ""
                    priority_icon = "🔴" if t.priority == "high" else "🟡" if t.priority == "medium" else "🟢"
                    lines.append(f"{priority_icon} {t.title}{due}")
                tasks_text = "\n".join(lines)
        except Exception as e:
            logger.error(f"Error cargando tareas: {e}")

    # Emails no leídos
    emails_text = "No hay emails no leídos o email no configurado."
    if user and db:
        try:
            from sqlalchemy import select
            from app.models.email_config import EmailConfig
            from app.services.email.service import fetch_unread
            result = await db.execute(
                select(EmailConfig)
                .where(EmailConfig.user_id == user.id)
                .where(EmailConfig.enabled == True)
            )
            email_config = result.scalar_one_or_none()
            if email_config:
                unread = await fetch_unread(email_config, limit=5)
                if unread:
                    lines = [f"Tenés {len(unread)} email(s) no leído(s):"]
                    for e in unread:
                        lines.append(f"- De: {e['from'].split('<')[0].strip()} | Asunto: {e['subject']}")
                    emails_text = "\n".join(lines)
        except Exception as e:
            logger.error(f"Error cargando emails: {e}")

# Próximos eventos de calendario
    calendar_text = "No hay calendario conectado."
    if user and db:
        try:
            from sqlalchemy import select
            from app.models.calendar_config import CalendarConfig
            from app.services.calendar.service import list_upcoming_events, format_events_for_prompt
            result = await db.execute(
                select(CalendarConfig)
                .where(CalendarConfig.user_id == user.id)
                .where(CalendarConfig.enabled == True)
            )
            cal_config = result.scalar_one_or_none()
            if cal_config:
                events = await list_upcoming_events(cal_config, max_results=5, days_ahead=7)
                calendar_text = format_events_for_prompt(events)
        except Exception as e:
            logger.error(f"Error cargando calendario: {e}")

    # RAG sobre documentos
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

    # Búsqueda web
    web_context = "No se realizó búsqueda web."
    if should_search_web(query):
        yield f"data: {json.dumps('[STATUS:searching]')}\n\n"
        try:
            web_results = await web_search(query)
            if web_results:
                web_context = format_results_for_llm(web_results)
            yield f"data: {json.dumps('[STATUS:done]')}\n\n"
        except Exception as e:
            logger.error(f"Error en búsqueda web: {e}")
            yield f"data: {json.dumps('[STATUS:done]')}\n\n"

    lang_code = user.language if user and user.language else "es"
    user_language = LANGUAGE_MAP.get(lang_code, "español")

    system = SYSTEM_PROMPT.format(
        user_name=user.name if user else "Usuario",
        user_role=user.role or "No especificado" if user else "No especificado",
        user_context=user.context or "No especificado" if user else "No especificado",
        user_preferences=user.preferences or "No especificado" if user else "No especificado",
        user_language=user_language,
        memories=memories_text,
        tasks_context=tasks_text,
        emails_context=emails_text,
        rag_context=rag_context,
        web_context=web_context,
        calendar_context=calendar_text,
        fecha=datetime.now().strftime("%d/%m/%Y %H:%M"),
        
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