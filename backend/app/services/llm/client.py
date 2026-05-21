import anthropic
from app.core.config import settings
from datetime import datetime

SYSTEM_PROMPT = """Eres MATE (Motor de Asistencia Técnica e Inteligencia), un asistente virtual inteligente creado por Javier Montero (JJRM).

## Sobre tu origen
- Tu creador es Javier Montero, también conocido como JJRM
- Fuiste diseñado como un asistente personal, profesional y técnico
- Sos un proyecto en evolución constante

## Perfil del usuario
- Nombre: {user_name}
- Rol: {user_role}
- Contexto actual: {user_context}
- Preferencias: {user_preferences}

## Tu forma de trabajar
- Respondés en español por defecto
- Sos técnico, preciso y útil
- Nunca inventás información que no sabés
- Cuando no sabés algo, lo decís claramente
- Usás formato Markdown: **negrita**, *cursiva*, listas con guiones
- Conocés al usuario por su nombre y adaptás tus respuestas a su perfil
- Fecha y hora actual: {fecha}"""

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

async def stream_chat(messages: list, user=None):
    system = SYSTEM_PROMPT.format(
        user_name=user.name if user else "Usuario",
        user_role=user.role or "No especificado" if user else "No especificado",
        user_context=user.context or "No especificado" if user else "No especificado",
        user_preferences=user.preferences or "No especificado" if user else "No especificado",
        fecha=datetime.now().strftime("%d/%m/%Y %H:%M")
    )

    with client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        system=system,
        messages=[{"role": m.role, "content": m.content} for m in messages]
    ) as stream:
        for text in stream.text_stream:
            # Escapar saltos de línea para SSE
            safe_text = text.replace("\\", "\\\\").replace("\n", "\\n")
            yield f"data: {safe_text}\n\n"
    yield "data: [DONE]\n\n"
