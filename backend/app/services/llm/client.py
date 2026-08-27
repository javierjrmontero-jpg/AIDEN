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
# Subconjunto SEGURO de herramientas para el chat conversacional.
# Reutiliza los schemas y el executor del agente (DRY). Se excluyen
# execute_python / execute_bash a propósito: la ejecución de código por
# lenguaje natural debe quedar solo en el agente autónomo, no en el chat.
CHAT_TOOL_NAMES = {
    "get_calendar_events",
    "create_calendar_event",
    "send_email",
    "create_task",
    # Read-only: sin efectos externos, seguras en el chat conversacional
    "search_documents",
    "read_memories",
}
CHAT_TOOLS = [t for t in RESEARCH_TOOLS if t["name"] in CHAT_TOOL_NAMES]


def _api_error_message(e: anthropic.APIError) -> str:
    """Mensaje legible para el usuario a partir de un error de la API."""
    detalle = str(getattr(e, "message", "") or e)
    if "credit balance is too low" in detalle:
        return ("⚠️ **Sin saldo en la cuenta de Anthropic.** Recargá créditos en "
                "console.anthropic.com → Plans & Billing para volver a usar el chat.")
    if isinstance(e, anthropic.RateLimitError):
        return "⚠️ **Límite de uso alcanzado.** Esperá unos minutos y volvé a intentar."
    if isinstance(e, anthropic.AuthenticationError):
        return "⚠️ **API key inválida.** Revisá `ANTHROPIC_API_KEY` en la configuración del servidor."
    if "prompt is too long" in detalle:
        return ("⚠️ **La conversación superó el contexto del modelo.** "
                "Empezá una conversación nueva para continuar.")
    return f"⚠️ **Error de la API de Anthropic:** {detalle}"

# Tope de iteraciones del bucle de herramientas por turno de chat (anti-loop).
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
- Podés BUSCAR en los documentos del usuario (search_documents) cuando pregunte sobre su contenido, y CONSULTAR memorias previas (read_memories) para recuperar preferencias o información personal memorizada.
- Para fechas relativas ("mañana", "el viernes a las 15") calculá la fecha y hora absolutas en formato ISO 8601 a partir de la fecha y hora actual indicada más abajo.
- Antes de ENVIAR un email, confirmá destinatario, asunto y contenido con el usuario si no te los dio explícitamente.
- Usá las herramientas solo cuando el usuario pida una acción concreta; para preguntas informativas respondé directamente.
- Después de ejecutar una acción, confirmá el resultado de forma breve y clara.

## Dev Agent — Ejecución de código en el Orbe (PRO)
Cuando el usuario pide calcular algo, ejecutar un script o hacer un cómputo que se resuelve bien con Python, podés emitir el marcador `[RUN_PY:código]` en tu respuesta. El Orbe de MATE detecta este marcador, ejecuta el código Python localmente en la PC del usuario y reemplaza el marcador por el resultado antes de hablar.

Reglas para usar [RUN_PY:]:
- Usalo SOLO cuando el usuario esté en modo voz (el mensaje contiene `[VOZ:`) o pida explícitamente ejecutar código.
- El código debe ser Python válido, simple y seguro. No puede hacer requests HTTP ni acceder a rutas absolutas del sistema.
- El marcador debe estar en una línea separada del texto: `[RUN_PY:print(2+2)]`
- El resultado (stdout) se inyecta en la respuesta TTS. Mantené el código breve para que el resultado sea legible por voz.
- Si el cálculo es simple (ej: multiplicar dos números), respondé directamente sin usar [RUN_PY:].
- Ejemplos válidos: cálculos de fechas, conversiones, estadísticas simples, listas de números.

Ejemplo de uso correcto:
Usuario: "¿cuántos días faltan para fin de año?"
Respuesta: "Faltan este número de días para el 31 de diciembre: [RUN_PY:from datetime import date; r=date(date.today().year,12,31)-date.today(); print(r.days)]"

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

async def stream_chat(messages: list, user=None, db=None, voice: bool = False):
    query = messages[-1].content

    # Memorias del usuario (SQLite plano + Graphiti grafo temporal)
    memories_text = "No hay memorias previas."
    if user and db:
        try:
            from app.services.memory.service import format_memories_for_prompt
            memories_text = await format_memories_for_prompt(db, user.id)
        except Exception as e:
            logger.error(f"Error cargando memorias: {e}")

    # Enriquecer con contexto de Graphiti si está disponible
    graphiti_context = ""
    if user:
        try:
            from app.services.memory.graphiti_service import get_context_for_prompt
            graphiti_context = await get_context_for_prompt(user.id, query)
            if graphiti_context:
                memories_text = f"{memories_text}\n\n{graphiti_context}"
        except Exception as e:
            logger.debug(f"Graphiti no disponible para contexto: {e}")

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

    # Próximos eventos de calendario
    calendar_text = "No hay calendario conectado."
    if user and db:
        try:
            from sqlalchemy import select
            from app.models.calendar_config import CalendarConfig
            from app.services.calendar.router import list_upcoming_events, format_events_for_prompt
            result = await db.execute(
                select(CalendarConfig)
                .where(CalendarConfig.user_id == user.id)
                .where(CalendarConfig.enabled == True)
            )
            eventos = []
            for cal_config in result.scalars().all():
                eventos.extend(await list_upcoming_events(cal_config, max_results=5, days_ahead=7))
            if eventos:
                eventos.sort(key=lambda e: e.get("start") or "")
                calendar_text = format_events_for_prompt(eventos)
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

    # --- Tool-loop: streaming + ejecución de herramientas hasta end_turn -----
    # Conversación mutable: arranca con los mensajes del usuario y va sumando
    # los turnos del asistente (texto + tool_use) y los tool_result.
    convo = [{"role": m.role, "content": m.content} for m in messages]

    for _turn in range(MAX_TOOL_TURNS):
        try:
            with client.messages.stream(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                system=system,
                tools=CHAT_TOOLS,
                messages=convo,
            ) as stream:
                # Streamea al cliente cualquier texto que el modelo emita en esta pasada
                for text in stream.text_stream:
                    payload = json.dumps(text, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                final = stream.get_final_message()
        except anthropic.APIError as e:
            logger.error(f"Error de la API de Anthropic en chat: {e}")
            aviso = _api_error_message(e)
            yield f"data: {json.dumps(aviso, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Guarda el turno completo del asistente (texto + bloques tool_use)
        convo.append({"role": "assistant", "content": final.content})

        # Si no pidió herramientas, terminó: salimos del bucle
        if final.stop_reason != "tool_use":
            break

        # Ejecuta cada herramienta solicitada y reinyecta los resultados
        tool_results = []
        for block in final.content:
            if block.type != "tool_use":
                continue
 
            tool_input = block.input if isinstance(block.input, dict) else vars(block.input)
             # --- GATE: send_email NO se ejecuta; se manda a confirmar -------
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
 
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
                continue
            # ----------------------------------------------------------------
 
            yield f"data: {json.dumps(f'[STATUS:tool:{block.name}]', ensure_ascii=False)}\n\n"
            try:
                result = await _execute_tool(block.name, tool_input, user, db)
            except Exception as e:
                logger.error(f"Error ejecutando tool {block.name} en chat: {e}")
                result = f"Error ejecutando '{block.name}': {e}"
 
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
            yield f"data: {json.dumps('[STATUS:done]')}\n\n"
 
        convo.append({"role": "user", "content": tool_results})
    else:
        # Se agotó MAX_TOOL_TURNS sin un end_turn limpio
        logger.warning("Tool-loop alcanzó MAX_TOOL_TURNS sin end_turn")
        aviso = "\n\n_(Se alcanzó el límite de pasos de herramientas en este turno.)_"
        yield f"data: {json.dumps(aviso, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
