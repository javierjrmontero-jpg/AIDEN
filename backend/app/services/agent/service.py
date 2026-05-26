import anthropic
import json
import logging
from app.core.config import settings
from app.services.search.service import web_search, format_results_for_llm
from app.services.sandbox.service import execute_code
from datetime import datetime

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

AGENT_TOOLS = [
    {
        "name": "web_search",
        "description": "Busca información actualizada en la web. Usá cuando necesitás datos recientes o específicos.",
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
        "description": "Ejecuta código Python para cálculos, análisis de datos o procesamiento.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "El código Python a ejecutar"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "create_document",
        "description": "Crea un documento con el contenido generado. Usá al final para entregar el resultado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título del documento"},
                "content": {"type": "string", "description": "Contenido en Markdown"},
                "format": {"type": "string", "description": "Formato: md, txt, html", "default": "md"}
            },
            "required": ["title", "content"]
        }
    }
]

async def run_agent(task: str, user=None, db=None):
    """
    Ejecuta el agente autónomo enviando eventos SSE con el progreso.
    Yields: eventos SSE con el estado de cada paso
    """
    messages = [{"role": "user", "content": task}]
    
    system = f"""Eres MATE, un agente autónomo inteligente creado por JJRM.
Tu objetivo es completar tareas complejas paso a paso usando las herramientas disponibles.

Reglas:
- Planificá antes de actuar
- Usá las herramientas en orden lógico
- Buscá información actualizada cuando sea necesario
- Al finalizar, siempre creá un documento con el resultado usando create_document
- Sé conciso en los pasos intermedios
- Fecha actual: {datetime.now().strftime('%d/%m/%Y %H:%M')}
- Usuario: {user.name if user else 'Usuario'}"""

    step = 0
    max_steps = 10

    yield f"data: {json.dumps({'type': 'start', 'message': 'Iniciando agente...'})}\n\n"

    while step < max_steps:
        step += 1

        try:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=system,
                tools=AGENT_TOOLS,
                messages=messages
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Agregar respuesta del asistente al historial
        messages.append({"role": "assistant", "content": response.content})

        # Procesar la respuesta
        if response.stop_reason == "end_turn":
            # Respuesta final sin herramientas
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            yield f"data: {json.dumps({'type': 'complete', 'message': final_text})}\n\n"
            return

        elif response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    yield f"data: {json.dumps({'type': 'step', 'tool': tool_name, 'input': str(tool_input)[:200]})}\n\n"

                    # Ejecutar la herramienta
                    result = ""
                    try:
                        if tool_name == "web_search":
                            results = await web_search(tool_input["query"], count=5)
                            result = format_results_for_llm(results) if results else "Sin resultados"

                        elif tool_name == "execute_python":
                            exec_result = await execute_code(tool_input["code"], "python")
                            if exec_result["success"]:
                                result = exec_result["output"] or "Código ejecutado sin output"
                            else:
                                result = f"Error: {exec_result['error']}"

                        elif tool_name == "create_document":
                            content = tool_input["content"]
                            title = tool_input.get("title", "documento")
                            result = f"Documento '{title}' creado con {len(content)} caracteres"
                            # Enviar el documento al frontend
                            yield f"data: {json.dumps({'type': 'document', 'title': title, 'content': content, 'format': tool_input.get('format', 'md')})}\n\n"

                    except Exception as e:
                        result = f"Error ejecutando {tool_name}: {str(e)}"
                        logger.error(f"Agent tool error: {e}")

                    yield f"data: {json.dumps({'type': 'result', 'tool': tool_name, 'result': str(result)[:300]})}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Agregar resultados al historial
            messages.append({"role": "user", "content": tool_results})

        else:
            # Stop reason desconocido
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Tarea completada.'})}\n\n"
            return

    yield f"data: {json.dumps({'type': 'error', 'message': 'Se alcanzó el límite de pasos del agente.'})}\n\n"
