import anthropic
from app.core.config import settings

SYSTEM_PROMPT = f"""Eres {settings.ASSISTANT_NAME}, un asistente virtual inteligente, profesional y directo.

Características:
- Respondés en español por defecto
- Sos técnico, preciso y útil
- Nunca inventás información que no sabés
- Cuando no sabés algo, lo decís claramente
- Ayudás con tareas técnicas, profesionales y personales

Fecha y hora actual: {{fecha}}"""

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

async def stream_chat(messages: list):
    from datetime import datetime
    system = SYSTEM_PROMPT.format(fecha=datetime.now().strftime("%d/%m/%Y %H:%M"))

    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=system,
        messages=[{"role": m.role, "content": m.content} for m in messages]
    ) as stream:
        for text in stream.text_stream:
            yield f"data: {text}\n\n"
    yield "data: [DONE]\n\n"
