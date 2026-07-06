import json
import logging
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)


async def stream_gemini(system: str, messages: list):
    """Stream chat via Google Gemini, yielding SSE-formatted chunks."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system,
    )

    gemini_messages = []
    for m in messages:
        role = m["role"] if isinstance(m, dict) else m.role
        content = m["content"] if isinstance(m, dict) else m.content
        # Gemini uses "user" and "model" roles
        gemini_role = "model" if role == "assistant" else "user"
        gemini_messages.append({"role": gemini_role, "parts": [content]})

    response = model.generate_content(
        gemini_messages,
        stream=True,
        generation_config={"max_output_tokens": 2048},
    )

    for chunk in response:
        if chunk.text:
            yield f"data: {json.dumps(chunk.text, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
