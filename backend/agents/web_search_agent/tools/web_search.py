import time

import structlog
from langchain.tools import tool
from pydantic import BaseModel, Field

from agents.web_search_agent.core.search import search
from api.services.agents.tools import (
    generate_error_message,
    generate_result_message,
    generate_status_message,
    generate_step_message,
)

log = structlog.get_logger(__name__)

# Entries older than this are evicted from the dedup cache.
CACHE_TTL_SECONDS = 60
# A similar query inside this window reuses the cached result (LLMs tend to fire duplicate searches).
DUPLICATE_WINDOW_SECONDS = 30
# Shared words needed to consider two queries "similar".
MIN_SHARED_WORDS = 2
# Preview length logged for a result.
RESULT_PREVIEW_CHARS = 100

# Controle global para evitar buscas duplas na mesma sessão
_search_cache = {}


class WebSearchInput(BaseModel):
    """Input para realizar uma busca na web."""

    query: str = Field(description="Query para realizar uma busca na web.")


@tool("web_search", args_schema=WebSearchInput)
async def web_search(query: str) -> str:
    """Ferramenta para realizar busca na web sobre qualquer tópico.

    Use esta ferramenta SEMPRE que precisar de informações sobre:
    - Pessoas específicas
    - Eventos atuais
    - Fatos ou dados específicos
    - Qualquer informação que não esteja em seu conhecimento base

    IMPORTANTE: Esta ferramenta já faz scraping de múltiplas páginas e resume automaticamente.
    UMA busca é suficiente para obter informações completas.

    Args:
        query: Query para realizar uma busca na web.

    Returns:
        String formatada com informações completas da busca na web.
    """

    log.info("web_search_tool_started", query=query)

    # Verificar se já foi feita uma busca similar recentemente
    query_normalized = query.lower().strip()
    current_time = time.time()

    # Limpar cache antigo (mais de 60 segundos)
    keys_to_remove = []
    for cached_query, (timestamp, _) in _search_cache.items():
        if current_time - timestamp > CACHE_TTL_SECONDS:
            keys_to_remove.append(cached_query)

    for key in keys_to_remove:
        del _search_cache[key]

    # Verificar se existe busca similar no cache
    for cached_query, (timestamp, cached_result) in _search_cache.items():
        # Se a query é muito similar e foi feita recentemente (últimos 30 segundos)
        if current_time - timestamp < DUPLICATE_WINDOW_SECONDS and (
            query_normalized in cached_query
            or cached_query in query_normalized
            or len(set(query_normalized.split()) & set(cached_query.split())) >= MIN_SHARED_WORDS
        ):
            cache_msg = generate_status_message(
                "completed", f"Usando resultado em cache para query similar: '{cached_query}'"
            )
            log.info("web_search_tool_cache_hit", message=cache_msg)
            return cached_result

    try:
        search_msg = generate_step_message(1, "Iniciando busca na web...")
        log.info("web_search_tool_step", message=search_msg)

        result = await search(query)

        # Armazenar no cache
        _search_cache[query_normalized] = (current_time, result)

        success_msg = generate_result_message(
            "success", f"Busca concluída! Resultado: {len(result) if result else 0} caracteres"
        )
        log.info(
            "web_search_tool_done",
            message=success_msg,
            preview=result[:RESULT_PREVIEW_CHARS] if result else "VAZIO",
        )
        return result
    except Exception as e:
        error_msg = generate_error_message(f"Erro inesperado ao realizar a busca na web: {e!s}")
        log.error("web_search_tool_failed", message=error_msg)
        return f"Erro inesperado ao realizar a busca na web: {e!s}"
