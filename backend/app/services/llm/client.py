import anthropic
import json
import logging
from app.core.config import settings
from app.services.rag.service import search_documents
from app.services.search.service import web_search, format_results_for_llm
from app.services.agent.service import (
    RESEARCH_TOOLS,
    _execute_tool,
    _resolve_email_account,
    _account_label,
)
from app.services.audit.service import write_audit
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

# --- Tool-loop en chat -------------------------------------------------------
CHAT_TOOL_NAMES = {
    "get_calendar_events",
    "create_calendar_event",
    "send_email",
    "create_task",
}
CHAT_TOOLS = [t for t in RESEARCH_TOOLS if t["name"] in CHAT_TOOL_NAMES]
MAX_TOOL_TURNS = 5
# -----------------------------------------------------------------------------

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

## Acciones disponibles (herramientas)
- Podés LEER la agenda, CREAR eventos de calendario, CREAR tareas y ENVIAR emails usando tus herramientas, cuando el usuario lo pida en lenguaje natural.
- Para fechas relativas ("mañana", "el viernes a las 15") calculá la fecha y hora absolutas en formato ISO 8601 a partir de la fecha y hora actual indicada más abajo.
- Antes de ENVIAR un email, confirmá destinatario, asunto y contenido con el usuario si no te los dio explícitamente.
- Usá las herramientas solo cuando el usuario pida una acción concreta; para preguntas informativas respondé directamente.
- Después de ejecutar una acción, confirmá el resultado de forma breve y clara.

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

    memories_text = "No hay memorias previas."
    if user and db:
        try:
            from app.services.memory.service import format_memories_for_prompt
            memories_text = await format_memories_for_prompt(db, user.id)
        except Exception as e:
            logger.error(f"Error cargando memorias: {e}")

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
            email_configs = result.scalars().all()
            all_unread = []
            for cfg in email_configs:
                try:
                    unread = await fetch_unread(cfg, limit=5)
                    all_unread.extend(unread)
                except Exception as ie:
                    logger.error(f"Error leyendo cuenta {cfg.id}: {ie}")
            if all_unread:
                lines = [f"Tenés {len(all_unread)} email(s) no leído(s):"]
                for e in all_unread:
                    lines.append(f"- De: {e['from'].split('<')[0].strip()} | Asunto: {e['subject']}")
                emails_text = "\n".join(lines)
        except Exception as e:
            logger.error(f"Error cargando emails: {e}")

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

    convo = [{"role": m.role, "content": m.content} for m in messages]

    for _turn in range(MAX_TOOL_TURNS):
        with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=system,
            tools=CHAT_TOOLS,
            messages=convo,
        ) as stream:
            for text in stream.text_stream:
                payload = json.dumps(text, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            final = stream.get_final_message()

        convo.append({"role": "assistant", "content": final.content})

        if final.stop_reason != "tool_use":
            break

        tool_results = []
        for block in final.content:
            if block.type != "tool_use":
                continue

            tool_input = block.input if isinstance(block.input, dict) else vars(block.input)

            # --- GATE: send_email → borrador para confirmar ------------------
            if block.name == "send_email":
                from sqlalchemy import select
                from app.models.email_config import EmailConfig

                r = await db.execute(
                    select(EmailConfig)
                    .where(EmailConfig.user_id == user.id)
                    .where(EmailConfig.enabled == True)
                )
                configs = r.scalars().all()

                if not configs:
                    result = "Error: no hay cuenta de email configurada."
                else:
                    cfg = _resolve_email_account(configs, tool_input.get("from_account"))
                    if cfg is None:
                        etiquetas = ", ".join(_account_label(c) for c in configs)
                        if tool_input.get("from_account"):
                            result = (f"No encontré la cuenta '{tool_input['from_account']}'. "
                                      f"Cuentas disponibles: {etiquetas}.")
                        else:
                            result = (f"Hay varias cuentas ({etiquetas}). "
                                      f"Indicá desde cuál enviar (from_account).")
                    else:
                        draft = {
                            "to": tool_input.get("to", ""),
                            "subject": tool_input.get("subject", ""),
                            "body": tool_input.get("body", ""),
                            "account_id": getattr(cfg, "id", None),
                            "account_label": _account_label(cfg),
                        }
                        marker = f"[CONFIRM_EMAIL:{json.dumps(draft, ensure_ascii=False)}]"
                        yield f"data: {json.dumps(marker, ensure_ascii=False)}\n\n"
                        result = ("Borrador de email preparado y mostrado al usuario. "
                                  "ESPERANDO su confirmación explícita. El email NO fue enviado.")

                # Audit: borrador de email en chat
                await write_audit(db, user.id, "chat", "send_email",
                                   tool_input, result,
                                   "success" if "borrador" in result else "error")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
                continue
            # -----------------------------------------------------------------

            yield f"data: {json.dumps(f'[STATUS:tool:{block.name}]', ensure_ascii=False)}\n\n"
            try:
                result = await _execute_tool(block.name, tool_input, user, db)
            except Exception as e:
                logger.error(f"Error ejecutando tool {block.name} en chat: {e}")
                result = f"Error ejecutando '{block.name}': {e}"

            # Audit: tool ejecutada en chat
            await write_audit(db, user.id, "chat", block.name,
                               tool_input, result,
                               "error" if result.startswith("Error") else "success")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
            yield f"data: {json.dumps('[STATUS:done]')}\n\n"

        convo.append({"role": "user", "content": tool_results})
    else:
        logger.warning("Tool-loop alcanzó MAX_TOOL_TURNS sin end_turn")
        aviso = "\n\n_(Se alcanzó el límite de pasos de herramientas en este turno.)_"
        yield f"data: {json.dumps(aviso, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
