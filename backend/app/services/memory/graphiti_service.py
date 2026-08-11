"""
MATE Graphiti Memory Service
Grafo de memoria temporal usando Graphiti (Zep AI) + Neo4j.

Variables de entorno necesarias en el backend .env:
  NEO4J_URI=bolt://neo4j:7687
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=mateneo4j2024

Si Neo4j no está disponible, todas las funciones degradan
silenciosamente y retornan vacío/False — nunca rompen el flujo principal.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_graphiti: Optional[object] = None
_graphiti_init_attempted = False


# ─── Custom embedder usando fastembed (ya instalado en el proyecto) ────────────

class _FastembedEmbedder:
    """
    Wrapper de fastembed para Graphiti.
    Implementa la interfaz EmbedderClient de graphiti-core.
    BAAI/bge-small-en-v1.5 → dim=384.
    """
    embedding_dim = 384

    def __init__(self):
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    async def create(self, input: list[str]) -> list[list[float]]:
        # fastembed es síncrono; ejecutar en thread pool para no bloquear el event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(self._model.embed(input)),
        )
        return [e.tolist() for e in embeddings]


# ─── Inicialización de Graphiti ───────────────────────────────────────────────

async def _init_graphiti():
    """Inicializa Graphiti una sola vez. Thread-safe mediante flag."""
    global _graphiti, _graphiti_init_attempted
    if _graphiti_init_attempted:
        return _graphiti
    _graphiti_init_attempted = True

    neo4j_uri  = os.getenv("NEO4J_URI",      "bolt://neo4j:7687")
    neo4j_user = os.getenv("NEO4J_USER",     "neo4j")
    neo4j_pass = os.getenv("NEO4J_PASSWORD", "mateneo4j2024")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    try:
        from graphiti_core import Graphiti
        from graphiti_core.llm_client.anthropic_client import (
            AnthropicClient, AnthropicConfig,
        )

        llm_client = AnthropicClient(
            config=AnthropicConfig(api_key=anthropic_key)
        )
        embedder = _FastembedEmbedder()

        g = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_pass,
            llm_client=llm_client,
            embedder=embedder,
        )
        await g.build_indices_and_constraints()
        _graphiti = g
        logger.info("Graphiti inicializado correctamente (Neo4j: %s)", neo4j_uri)
    except ImportError:
        logger.warning("graphiti-core no instalado — memoria de grafo deshabilitada")
    except Exception as e:
        logger.warning("Graphiti no disponible: %s", e)

    return _graphiti


async def _get_graphiti():
    if _graphiti is not None:
        return _graphiti
    return await _init_graphiti()


# ─── API pública ──────────────────────────────────────────────────────────────

async def add_episode(
    user_id: str,
    content: str,
    role: str = "assistant",
    source_description: str = "MATE conversation",
) -> bool:
    """
    Agrega un episodio de conversación al grafo de memoria.
    Llamar desde chat.py después de cada turno guardado.
    """
    g = await _get_graphiti()
    if g is None:
        return False
    try:
        from graphiti_core.nodes import EpisodeType
        name = f"conv_{user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        await g.add_episode(
            name=name,
            episode_body=content,
            source=EpisodeType.message,
            source_description=source_description,
            reference_time=datetime.now(timezone.utc),
            group_id=user_id,
        )
        return True
    except Exception as e:
        logger.error("Error add_episode Graphiti: %s", e)
        return False


async def search_memory(
    user_id: str,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """
    Busca en el grafo de memoria por similitud semántica + temporal.
    Retorna lista de hechos extraídos.
    """
    g = await _get_graphiti()
    if g is None:
        return []
    try:
        results = await g.search(
            query=query,
            group_ids=[user_id],
            num_results=limit,
        )
        out = []
        for edge in results.edges:
            out.append({
                "fact": edge.fact,
                "valid_at": edge.valid_at.isoformat() if edge.valid_at else None,
                "invalid_at": edge.invalid_at.isoformat() if edge.invalid_at else None,
            })
        return out
    except Exception as e:
        logger.error("Error search_memory Graphiti: %s", e)
        return []


async def get_context_for_prompt(user_id: str, query: str = "") -> str:
    """
    Retorna un bloque de contexto listo para insertar en el SYSTEM_PROMPT.
    Combina hechos relevantes del grafo con el query actual del usuario.
    Retorna "" si Graphiti no está disponible.
    """
    q = query or "usuario proyectos trabajo preferencias tecnología"
    facts = await search_memory(user_id, q, limit=6)
    if not facts:
        return ""
    lines = []
    for f in facts:
        validity = ""
        if f.get("invalid_at"):
            validity = " [desactualizado]"
        elif f.get("valid_at"):
            try:
                dt = datetime.fromisoformat(f["valid_at"])
                validity = f" ({dt.strftime('%d/%m/%Y')})"
            except Exception:
                pass
        lines.append(f"- {f['fact']}{validity}")
    return "## Grafo de memoria (Graphiti)\n" + "\n".join(lines)


async def get_graph_summary(user_id: str) -> str:
    """Resumen del grafo de memoria para el endpoint /api/v1/memory/graph."""
    facts = await search_memory(user_id, "usuario", limit=10)
    if not facts:
        return "El grafo de memoria está vacío o Graphiti no está disponible."
    lines = [f"- {f['fact']}" for f in facts]
    return f"Tenés {len(facts)} hecho(s) en el grafo:\n" + "\n".join(lines)


async def is_available() -> bool:
    """Verifica si Graphiti está disponible."""
    g = await _get_graphiti()
    return g is not None
