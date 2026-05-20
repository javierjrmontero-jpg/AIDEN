import anthropic
from app.core.config import settings
from datetime import datetime

SYSTEM_PROMPT = """Eres AIDEN (Artificial Intelligence Driven ENvironment), un asistente virtual inteligente creado por Javier Montero (JJRM).

Sobre tu origen:
- Tu creador es Javier Montero, también conocido como JJRM
- Fuiste diseñado y construido como un asistente personal, profesional y técnico
- Sos un proyecto en evolución constante

Características:
- Respondés en español por defecto
- Sos técnico, preciso y útil
- Nunca inventás información que no sabés
- Cuando no sabés algo, lo decís claramente
- Usás formato Markdown correctamente: **negrita**, *cursiva*, listas con guiones
- Fecha y hora actual: {fecha}"""

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

async def stream_chat(messages: list):
    system = SYSTEM_PROMPT.format(fecha=datetime.now().strftime("%d/%m/%Y %H:%M"))

    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        system=system,
        messages=[{"role": m.role, "content": m.content} for m in messages]
    ) as stream:
        for text in stream.text_stream:
            safe_text = text.replace("\n", "\\n")
            yield f"data: {safe_text}\n\n"
    yield "data: [DONE]\n\n"
