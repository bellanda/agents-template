from langchain.tools import tool
from pydantic import BaseModel, Field

from utilities.web_search import search


class WebSearchInput(BaseModel):
    """Input para realizar uma busca na web."""

    query: str = Field(description="Query para realizar uma busca na web.")


@tool("web_search", args_schema=WebSearchInput, return_direct=False)
def web_search(query: str) -> str:
    """Ferramenta para realizar busca na web sobre qualquer tópico.

    Use esta ferramenta SEMPRE que precisar de informações sobre:
    - Pessoas específicas
    - Eventos atuais
    - Fatos ou dados específicos
    - Qualquer informação que não esteja em seu conhecimento base

    Args:
        query: Query para realizar uma busca na web.

    Returns:
        String formatada com informações completas da busca na web.
    """

    print(f"🚨 [TOOL] web_search EXECUTANDO com query: '{query}'")
    print(f"🚨 [TOOL] Timestamp: {__import__('time').time()}")

    try:
        print("🔍 [TOOL] Iniciando busca...")
        result = search(query)
        print(f"✅ [TOOL] Busca concluída! Resultado: {len(result) if result else 0} caracteres")
        print(f"📄 [TOOL] Primeiros 100 chars: {result[:100] if result else 'VAZIO'}...")
        return result
    except Exception as e:
        error_msg = f"Erro inesperado ao realizar a busca na web: {str(e)}"
        print(f"❌ [TOOL] ERRO: {error_msg}")
        return error_msg
