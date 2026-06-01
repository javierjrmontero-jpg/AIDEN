import anthropic
import json
import logging
import uuid

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.services.search.service import web_search, format_results_for_llm
from app.services.sandbox.service import execute_code
from app.services.rag.service import search_documents
from app.services.memory.service import get_memories
from app.services.email.service import send_email
from app.models.task import Task
from app.models.email_config import EmailConfig
from app.services.calendar.service import list_upcoming_events, create_event, format_events_for_prompt
from app.models.calendar_config import CalendarConfig

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

RESEARCH_TOOLS = [
    {
        "name": "web_search",
        "description": "Busca información actualizada en la web.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "execute_python",
        "description": "Ejecuta código Python para cálculos o análisis.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"]
        }
    },
    {
        "name": "execute_bash",
        "description": "Ejecuta scripts Bash para operaciones de sistema.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"]
        }
    },
    {
        "name": "search_documents",
        "description": "Busca en los documentos personales del usuario (PDFs, Word, texto).",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "read_memories",
        "description": "Lee las memorias y contexto personal del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
            "required": []
        }
    },
    {
        "name": "create_task",
        "description": "Crea una tarea o recordatorio en el sistema del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":       {"type": "string"},
                "description": {"type": "string"},
                "priority":    {"type": "string", "default": "medium"},
                "due_date":    {"type": "string", "description": "ISO 8601, ej: 2026-06-01T18:00:00"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "send_email",
        "description": "Envía un email usando la cuenta configurada del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string"},
                "subject": {"type": "string"},
                "body":    {"type": "string"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "get_calendar_events",
        "description": "Lee los próximos eventos del calendario del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days":  {"type": "integer", "default": 7},
                "limit": {"type": "integer", "default": 10}
            },
            "required": []
        }
    },
    {
        "name": "create_calendar_event",
        "description": "Crea un evento en el calendario del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary":     {"type": "string"},
                "start":       {"type": "string", "description": "ISO 8601, ej: 2026-06-01T18:00:00 (o 2026-06-01 día completo)"},
                "end":         {"type": "string", "description": "ISO 8601 opcional; por defecto +1h"},
                "description": {"type": "string"},
                "location":    {"type": "string"}
            },
            "required": ["summary", "start"]
        }
    }
]

DOCUMENT_TOOL = [
    {
        "name": "create_document",
        "description": "Crea el documento final con todo el contenido.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":   {"type": "string"},
                "content": {"type": "string"},
                "format":  {"type": "string", "default": "md"}
            },
            "required": ["title", "content"]
        }
    }
]


async def _execute_tool(tool_name: str, tool_input: dict, user, db: AsyncSession) -> str:
    try:
        if tool_name == "web_search":
            results = await web_search(tool_input["query"], count=5)
            return format_results_for_llm(results) if results else "Sin resultados."

        elif tool_name == "execute_python":
            r = await execute_code(tool_input["code"], "python")
            return r["output"] if r["success"] else f"Error: {r['error']}"

        elif tool_name == "execute_bash":
            r = await execute_code(tool_input["code"], "bash")
            return r["output"] if r["success"] else f"Error: {r['error']}"

        elif tool_name == "search_documents":
            results = search_documents(user.id, tool_input["query"], n_results=5)
            if not results:
                return "No se encontraron documentos relevantes."
            return "\n\n".join([f"[{r['filename']}]: {r['text']}" for r in results])

        elif tool_name == "read_memories":
            memories = await get_memories(db, user.id, limit=tool_input.get("limit", 10))
            if not memories:
                return "No hay memorias guardadas."
            return "\n".join([f"- {m.content}" for m in memories])

        elif tool_name == "create_task":
            due = None
            if tool_input.get("due_date"):
                try:
                    due = datetime.fromisoformat(tool_input["due_date"])
                except ValueError:
                    pass
            task = Task(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=tool_input["title"],
                description=tool_input.get("description", ""),
                priority=tool_input.get("priority", "medium"),
                due_date=due
            )
            db.add(task)
            await db.commit()
            return f"Tarea creada: '{task.title}' (prioridad: {task.priority})"

        elif tool_name == "send_email":
            result = await db.execute(
                select(EmailConfig).where(EmailConfig.user_id == user.id)
            )
            config = result.scalar_one_or_none()
            if not config:
                return "Error: no hay cuenta de email configurada."
            success = await send_email(config, to=tool_input["to"],
                                       subject=tool_input["subject"], body=tool_input["body"])
            return f"Email enviado a {tool_input['to']}." if success else "Error al enviar el email."

        elif tool_name == "get_calendar_events":
            r = await db.execute(
                select(CalendarConfig)
                .where(CalendarConfig.user_id == user.id)
                .where(CalendarConfig.enabled == True)
            )
            cfg = r.scalar_one_or_none()
            if not cfg:
                return "No hay calendario conectado."
            events = await list_upcoming_events(
                cfg, max_results=tool_input.get("limit", 10), days_ahead=tool_input.get("days", 7)
            )
            return format_events_for_prompt(events)

        elif tool_name == "create_calendar_event":
            r = await db.execute(
                select(CalendarConfig)
                .where(CalendarConfig.user_id == user.id)
                .where(CalendarConfig.enabled == True)
            )
            cfg = r.scalar_one_or_none()
            if not cfg:
                return "Error: no hay calendario conectado."
            ev = await create_event(
                cfg,
                summary=tool_input["summary"],
                start_iso=tool_input["start"],
                end_iso=tool_input.get("end", ""),
                description=tool_input.get("description", ""),
                location=tool_input.get("location", ""),
            )
            return f"Evento creado: '{ev['summary']}' el {ev['start']}. {ev.get('html_link','')}"

        return f"Herramienta '{tool_name}' no reconocida."

    except Exception as e:
        logger.error(f"Error en {tool_name}: {e}")
        return f"Error: {str(e)}"


async def run_agent(task: str, user=None, db=None):
    yield f"data: {json.dumps({'type': 'start', 'message': 'Iniciando investigación...'})}\n\n"

    research_messages = [{
        "role": "user",
        "content": (
            f"Resolvé esta tarea usando las herramientas disponibles.\n"
            f"Tarea: {task}\n\n"
            f"Usá las herramientas más adecuadas: web, documentos, memorias, código, tareas, email, calendario."
        )
    }]

    system_research = (
        f"Sos un agente autónomo con múltiples herramientas. "
        f"Resolvé la tarea usando las herramientas necesarias. "
        f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
        f"Usuario: {user.name if user else 'Usuario'}"
    )

    collected_info = []
    step = 0

    while step < 8:
        step += 1
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                system=system_research,
                tools=RESEARCH_TOOLS,
                messages=research_messages
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        research_messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_input = block.input if isinstance(block.input, dict) else vars(block.input)

                yield f"data: {json.dumps({'type': 'step', 'tool': block.name, 'input': str(tool_input)[:200]})}\n\n"

                result = await _execute_tool(block.name, tool_input, user, db)
                collected_info.append(f"## {block.name}\n{result}")

                yield f"data: {json.dumps({'type': 'result', 'tool': block.name, 'result': str(result)[:300]})}\n\n"
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

            research_messages.append({"role": "user", "content": tool_results})

    # FASE 2: Documento final
    yield f"data: {json.dumps({'type': 'step', 'tool': 'create_document', 'input': 'Generando documento final...'})}\n\n"

    all_info = "\n\n".join(collected_info) if collected_info else "Sin información adicional."

    try:
        doc_response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            tools=DOCUMENT_TOOL,
            tool_choice={"type": "tool", "name": "create_document"},
            messages=[{"role": "user", "content": (
                f"Creá un documento completo en Markdown.\n"
                f"TAREA: {task}\n\nINFORMACIÓN:\n{all_info}"
            )}]
        )

        for block in doc_response.content:
            if block.type != "tool_use" or block.name != "create_document":
                continue
            inp = block.input if isinstance(block.input, dict) else vars(block.input)
            content = inp.get("content", "")
            if not content:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Documento vacío.'})}\n\n"
                return
            yield f"data: {json.dumps({'type': 'document', 'title': inp.get('title', 'documento'), 'content': content, 'format': inp.get('format', 'md')})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'message': ''})}\n\n"
            return

    except Exception as e:
        logger.error(f"Error generando documento: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': f'Error generando documento: {str(e)}'})}\n\n"

    yield f"data: {json.dumps({'type': 'complete', 'message': 'Tarea completada.'})}\n\n"
