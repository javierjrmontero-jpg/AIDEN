import json
import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


async def stream_openai(system: str, messages: list):
    """Stream chat via OpenAI, yielding SSE-formatted chunks."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    openai_messages = [{"role": "system", "content": system}]
    for m in messages:
        role = m["role"] if isinstance(m, dict) else m.role
        content = m["content"] if isinstance(m, dict) else m.content
        openai_messages.append({"role": role, "content": content})

    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=openai_messages,
        stream=True,
        max_tokens=2048,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield f"data: {json.dumps(delta, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
