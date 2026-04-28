from langchain.tools import tool
from pydantic import BaseModel, Field

from agents.web_search_agent.core.search import search
from api.services.agents.tools import (
    generate_error_message,
    generate_result_message,
    generate_status_message,
    generate_step_message,
)

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

    print(f"🚨 [TOOL] web_search EXECUTANDO com query: '{query}'")
    print(f"🚨 [TOOL] Timestamp: {__import__('time').time()}")

    # Verificar se já foi feita uma busca similar recentemente
    query_normalized = query.lower().strip()
    current_time = __import__("time").time()

    # Limpar cache antigo (mais de 60 segundos)
    keys_to_remove = []
    for cached_query, (timestamp, result) in _search_cache.items():
        if current_time - timestamp > 60:
            keys_to_remove.append(cached_query)

    for key in keys_to_remove:
        del _search_cache[key]

    # Verificar se existe busca similar no cache
    for cached_query, (timestamp, cached_result) in _search_cache.items():
        # Se a query é muito similar e foi feita recentemente (últimos 30 segundos)
        if current_time - timestamp < 30 and (
            query_normalized in cached_query
            or cached_query in query_normalized
            or len(set(query_normalized.split()) & set(cached_query.split())) >= 2
        ):
            cache_msg = generate_status_message(
                "completed", f"Usando resultado em cache para query similar: '{cached_query}'"
            )
            print(f"🔄 [TOOL] {cache_msg}")
            return cached_result

    try:
        search_msg = generate_step_message(1, "Iniciando busca na web...")
        print(f"🔍 [TOOL] {search_msg}")

        result = await search(query)

        # Armazenar no cache
        _search_cache[query_normalized] = (current_time, result)

        success_msg = generate_result_message(
            "success", f"Busca concluída! Resultado: {len(result) if result else 0} caracteres"
        )
        print(f"✅ [TOOL] {success_msg}")
        print(f"📄 [TOOL] Primeiros 100 chars: {result[:100] if result else 'VAZIO'}...")
        return result
    except Exception as e:
        error_msg = generate_error_message(f"Erro inesperado ao realizar a busca na web: {e!s}")
        print(f"❌ [TOOL] {error_msg}")
        return f"Erro inesperado ao realizar a busca na web: {e!s}"
