import anthropic
import json
import logging
from app.core.config import settings
from app.services.search.service import web_search, format_results_for_llm
from app.services.sandbox.service import execute_code
from datetime import datetime

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

RESEARCH_TOOLS = [
    {
        "name": "web_search",
        "description": "Busca información actualizada en la web.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "La búsqueda a realizar"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "execute_python",
        "description": "Ejecuta código Python para cálculos o análisis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "El código Python a ejecutar"}
            },
            "required": ["code"]
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
                "title": {"type": "string", "description": "Título del documento"},
                "content": {"type": "string", "description": "Contenido completo en Markdown"},
                "format": {"type": "string", "description": "Formato: md, txt, html", "default": "md"}
            },
            "required": ["title", "content"]
        }
    }
]

async def run_agent(task: str, user=None, db=None):
    yield f"data: {json.dumps({'type': 'start', 'message': 'Iniciando investigación...'})}\n\n"

    # FASE 1: Recopilar información
    research_messages = [{
        "role": "user",
        "content": f"Investigá sobre este tema haciendo búsquedas web. Tarea: {task}"
    }]

    system_research = f"""Eres un investigador. Tu único trabajo es buscar información usando web_search.
Hacé 2-3 búsquedas relevantes sobre el tema solicitado.
Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}"""

    collected_info = []
    step = 0

    while step < 5:
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
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    yield f"data: {json.dumps({'type': 'step', 'tool': tool_name, 'input': str(tool_input)[:200]})}\n\n"

                    result = ""
                    try:
                        if tool_name == "web_search":
                            results = await web_search(tool_input["query"], count=5)
                            result = format_results_for_llm(results) if results else "Sin resultados"
                            collected_info.append(f"## Búsqueda: {tool_input['query']}\n{result}")
                        elif tool_name == "execute_python":
                            exec_result = await execute_code(tool_input["code"], "python")
                            result = exec_result["output"] if exec_result["success"] else f"Error: {exec_result['error']}"
                            collected_info.append(f"## Código ejecutado\nOutput: {result}")
                    except Exception as e:
                        result = f"Error: {str(e)}"

                    yield f"data: {json.dumps({'type': 'result', 'tool': tool_name, 'result': str(result)[:200]})}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            research_messages.append({"role": "user", "content": tool_results})

    # FASE 2: Generar documento (forzado)
    yield f"data: {json.dumps({'type': 'step', 'tool': 'create_document', 'input': 'Generando documento final...'})}\n\n"

    all_info = "\n\n".join(collected_info) if collected_info else "No se encontró información específica."

    doc_messages = [{
        "role": "user",
        "content": f"""Basándote en esta información recopilada, creá un documento completo y bien estructurado en Markdown.

TAREA ORIGINAL: {task}

INFORMACIÓN RECOPILADA:
{all_info}

Usá create_document con el contenido completo y bien formateado."""
    }]

    try:
        doc_response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            tools=DOCUMENT_TOOL,
            tool_choice={"type": "tool", "name": "create_document"},
            messages=doc_messages
        )

        for block in doc_response.content:
            if block.type == "tool_use" and block.name == "create_document":
                if isinstance(block.input, dict):
                    content = block.input.get("content", "")
                    title = block.input.get("title", "documento")
                    fmt = block.input.get("format", "md")
                else:
                    content = getattr(block.input, "content", "")
                    title = getattr(block.input, "title", "documento")
                    fmt = getattr(block.input, "format", "md")

                if not content:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Error: documento vacío'})}\n\n"
                    return

                yield f"data: {json.dumps({'type': 'document', 'title': title, 'content': content, 'format': fmt})}\n\n"
                yield f"data: {json.dumps({'type': 'complete', 'message': ''})}\n\n"
                return

    except Exception as e:
        logger.error(f"Error generando documento: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': f'Error generando documento: {str(e)}'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'complete', 'message': 'Investigación completada.'})}\n\n"
