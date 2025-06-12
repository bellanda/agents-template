import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from api.utils.tools import generate_error_message, generate_result_message, generate_status_message, generate_step_message
from utilities.web_search.duckduckgo import search as search_duckduckgo
from utilities.web_search.scrapper import scrape_url

BASE_DIR = pathlib.Path(__file__).parent.parent.parent


def search(query: str) -> str:
    """
    Realiza uma busca completa na web usando DuckDuckGo e faz scraping das páginas encontradas.

    Args:
        query: Termo de busca

    Returns:
        String com o conteúdo consolidado das páginas encontradas
    """
    try:
        # Passo 1: Buscar no DuckDuckGo
        search_msg = generate_step_message(1, f"Iniciando busca para: '{query}'")
        print(f"🔍 [SEARCH] {search_msg}")

        results = search_duckduckgo(query)

        results_msg = generate_result_message("success", f"Encontrados {len(results)} resultados do DuckDuckGo")
        print(f"📊 [SEARCH] {results_msg}")

        if not results:
            return "Nenhum resultado encontrado para a busca."

        # Limitar a 5 resultados para evitar sobrecarga
        results = results[:5]

        # Passo 2: Fazer scraping das páginas em paralelo
        scraping_msg = generate_step_message(2, f"Iniciando scraping paralelo de {len(results)} páginas...")
        print(f"🚀 [SEARCH] {scraping_msg}")

        scraped_contents = []
        successful_scrapes = 0
        failed_scrapes = 0

        # Usar ThreadPoolExecutor para scraping paralelo
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submeter todas as tarefas de scraping
            future_to_result = {executor.submit(scrape_url, result["url"]): result for result in results}

            # Processar resultados conforme completam
            for i, future in enumerate(as_completed(future_to_result)):
                result = future_to_result[future]
                try:
                    content = future.result()
                    if content and len(content.strip()) > 100:  # Só aceitar conteúdo substancial
                        scraped_contents.append(f"=== {result['title']} ===\nURL: {result['url']}\nConteúdo:\n{content}\n\n")
                        successful_scrapes += 1

                        success_msg = generate_result_message("success", f"Página {i + 1} processada: {result['url']}")
                        print(f"✅ [SEARCH] {success_msg}")
                    else:
                        failed_scrapes += 1
                        fail_msg = generate_status_message("warning", f"Página {i + 1} falhou: {result['url']}")
                        print(f"⚠️ [SEARCH] {fail_msg}")

                except Exception as e:
                    failed_scrapes += 1
                    error_msg = generate_error_message(f"Erro na página {i + 1}: {str(e)}")
                    print(f"❌ [SEARCH] {error_msg}")

        # Passo 3: Consolidar resultados
        if scraped_contents:
            consolidated_content = "\n".join(scraped_contents)

            # Limitar tamanho do conteúdo (máximo ~8000 caracteres)
            if len(consolidated_content) > 8000:
                consolidated_content = consolidated_content[:8000] + "\n\n[Conteúdo truncado devido ao tamanho...]"

            summary_msg = generate_result_message(
                "success", f"Resumo: {successful_scrapes} sucessos, {failed_scrapes} falhas de {len(results)} páginas"
            )
            print(f"📈 [SEARCH] {summary_msg}")

            return consolidated_content
        else:
            return "Não foi possível extrair conteúdo útil das páginas encontradas."

    except Exception as e:
        error_msg = generate_error_message(f"Erro durante a busca: {str(e)}")
        print(f"❌ [SEARCH] {error_msg}")
        return f"Erro durante a busca: {str(e)}"


if __name__ == "__main__":
    search("Gustavo Bellanda")
