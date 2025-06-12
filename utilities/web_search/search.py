import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

# from llms.nvidia import call_nvidia_llm
from llms.google import call_google_llm
from utilities.web_search.duckduckgo import search as search_duckduckgo
from utilities.web_search.scrapper import perform_scraping

BASE_DIR = pathlib.Path(__file__).parent.parent.parent


def scrape_single_result(result_with_index):
    """Função auxiliar para fazer scraping de uma única página"""
    i, result = result_with_index
    content = perform_scraping(result["url"])
    return i, result, content


def search(query: str) -> str:
    print(f"🔍 [SEARCH] Iniciando busca para: '{query}'")
    results = search_duckduckgo(query)
    print(f"📊 [SEARCH] Encontrados {len(results)} resultados do DuckDuckGo")

    full_content = ""
    successful_scrapes = 0
    failed_scrapes = 0

    # Usar ThreadPoolExecutor para fazer scraping em paralelo
    print(f"🚀 [SEARCH] Iniciando scraping paralelo de {len(results)} páginas...")

    # Preparar dados para o ThreadPoolExecutor
    results_with_index = [(i, result) for i, result in enumerate(results)]
    scraped_results = {}

    # Executar scraping em paralelo
    with ThreadPoolExecutor(max_workers=min(len(results), 10)) as executor:
        # Submeter todas as tarefas
        future_to_index = {
            executor.submit(scrape_single_result, result_with_index): result_with_index[0]
            for result_with_index in results_with_index
        }

        # Processar resultados conforme completam
        for future in as_completed(future_to_index):
            try:
                i, result, content = future.result()
                scraped_results[i] = (result, content)

                # Verifica se o scraping foi bem-sucedido
                if content.startswith("ERRO_"):
                    failed_scrapes += 1
                    print(f"⚠️ [SEARCH] Página {i + 1} falhou: {result['url']}")
                else:
                    successful_scrapes += 1
                    print(f"✅ [SEARCH] Página {i + 1} processada: {result['url']}")

            except Exception as e:
                i = future_to_index[future]
                failed_scrapes += 1
                print(f"❌ [SEARCH] Erro na página {i + 1}: {str(e)}")
                # Adicionar resultado com erro
                scraped_results[i] = (results[i], f"ERRO_EXCEPTION: {str(e)}")

    # Montar o conteúdo final na ordem original
    for i in range(len(results)):
        if i in scraped_results:
            result, content = scraped_results[i]
            full_content += f"Página {i + 1}\nURL: {result['url']}\nTítulo: {result['title']}\nDescrição: {result['description']}\n\n{content}\n\n"

    print(f"📈 [SEARCH] Resumo: {successful_scrapes} sucessos, {failed_scrapes} falhas de {len(results)} páginas")

    prompt = f"""
        Você é um analista de conteúdos da web especializado em condensar grandes volumes de texto.

        ## Objetivo
        Receber **exatamente 5** páginas completas — cada uma no formato:

        ### <Título da Página N>
        <corpo completo da Página N>

        e devolver **uma resposta única em Markdown** que:
        1. Contém todas as informações essenciais (fatos, números, datas, nomes, conclusões).
        2. Elimina repetições e detalhes triviais (ex.: código-fonte, anúncios, botões).
        3. Resolve possíveis contradições ou indica divergências, se houver.
        4. Já esteja pronta para ser exibida no front-end (não precisa de pós-processamento).

        ## Passos internos (Chain-of-Thought oculto)  
        1. **Para cada página**: extraia  
        • Tópicos centrais  
        • Dados quantitativos e citações relevantes  
        • Conclusão ou insight principal  
        2. **Agrupe** tópicos semelhantes das cinco páginas e integre informações complementares.  
        3. **Detecte incoerências**: se dois textos divergem, aponte brevemente (“Fonte A diz X, Fonte B diz Y”).  
        4. **Monte o resumo final** (veja formato abaixo).

        ## Formato de saída (exporte **apenas** o texto abaixo)  
        > Use **Markdown**, cabeçalhos, bullets e **emojis** 👀 para tornar a visualização agradável.  
        > Inclua o **link da URL** de cada página onde indicado.

        **Resumo Integrado**  
        (Escreva de forma clara e concisa; escolha um tamanho que cubra todos os pontos essenciais sem se alongar demais.)

        **Principais Pontos Organizados**  
        - 🔹 *Tópico 1*: frase-síntese + dados / exemplos  
        - 🔹 *Tópico 2*: …  
        *(Máx. 7 bullets.)*

        **Notas de Divergência ⚠️ (opcional)**  
        - Se houver conflito: “Página 1 vs Página 3: …”

        **Mapa de Origem**  
        [🔗 Página 1 – Título](URL-1) → ideia-chave-1, ideia-chave-2  
        [🔗 Página 2 – Título](URL-2) → …  
        *(Liste apenas as ideias condensadas — não copie texto literal.)*

        ## Regras
        - Escreva em **português** claro.
        - Não invente informações; baseie-se somente no texto das páginas.
        - Se faltar uma das 5 páginas, mencione: “Aviso: página X ausente”.  
        - Evite blocos de código; use formatação simples de Markdown.
        
        CONTEÚDO:
        ```text
        {full_content}
        ```
    """
    # Create scrapper directory
    SCRAPPER_DIR = BASE_DIR / "data/scrapper"
    SCRAPPER_DIR.mkdir(parents=True, exist_ok=True)

    # Save raw web search results
    RAW_WEB_SEARCH_RESULTS_FILE = SCRAPPER_DIR / "raw_web_search_results.txt"
    with open(RAW_WEB_SEARCH_RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(full_content)

    # Summarize web search results
    # result_summarized = call_nvidia_llm("meta/llama-4-scout-17b-16e-instruct", prompt, max_tokens=1024)
    result_summarized = call_google_llm("gemini-2.0-flash-lite", prompt, max_tokens=1024)

    # Save summarized web search results
    SUMMARIZED_WEB_SEARCH_RESULTS_FILE = SCRAPPER_DIR / "summarized_web_search_results.txt"
    with open(SUMMARIZED_WEB_SEARCH_RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(result_summarized)

    return result_summarized


if __name__ == "__main__":
    search("Gustavo Bellanda")
