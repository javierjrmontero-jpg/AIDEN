import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_COST_PER_1000 = 5.0  # USD por 1000 requests

async def web_search(query: str, count: int = 5, user_id: str = None, db=None) -> list:
    if not settings.BRAVE_SEARCH_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BRAVE_URL,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY
                },
                params={
                    "q": query,
                    "count": count,
                    "search_lang": "es",
                    "country": "AR",
                    "text_decorations": False,
                    "safesearch": "moderate"
                }
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "date": item.get("page_age", "")
                })

            logger.info(f"Búsqueda web: '{query}' → {len(results)} resultados")

            # Registrar uso si se pasó db y user_id
            if db and user_id:
                try:
                    from app.models.usage import SearchUsage
                    import uuid
                    from datetime import datetime
                    usage = SearchUsage(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        query=query,
                        results_count=len(results),
                        created_at=datetime.utcnow()
                    )
                    db.add(usage)
                    await db.commit()
                except Exception as e:
                    logger.error(f"Error registrando uso: {e}")

            return results

    except Exception as e:
        logger.error(f"Error en búsqueda web: {e}")
        return []

def format_results_for_llm(results: list) -> str:
    if not results:
        return ""
    lines = ["## Resultados de búsqueda web\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"**{i}. {r['title']}**")
        if r.get("date"):
            lines.append(f"*Fecha: {r['date']}*")
        lines.append(r["description"])
        lines.append(f"Fuente: {r['url']}\n")
    return "\n".join(lines)
