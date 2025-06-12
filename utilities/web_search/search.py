import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from llms.nvidia import call_nvidia_llm
from utilities.web_search.duckduckgo import search as search_duckduckgo
from utilities.web_search.scrapper import perform_scraping

BASE_DIR = pathlib.Path(__file__).parent.parent.parent


def search(query: str) -> str:
    print(f"🔍 [SEARCH] Iniciando busca para: '{query}'")
    results = search_duckduckgo(query)
    print(f"📊 [SEARCH] Encontrados {len(results)} resultados do DuckDuckGo")

    full_content = ""

    for i, result in enumerate(results):
        content = perform_scraping(result["url"])
        full_content += f"Página {i + 1}\nURL: {result['url']}\nTítulo: {result['title']}\nDescrição: {result['description']}\n\n{content}\n\n"

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
    result_summarized = call_nvidia_llm("meta/llama-4-scout-17b-16e-instruct", prompt, max_tokens=1024)

    # Save summarized web search results
    SUMMARIZED_WEB_SEARCH_RESULTS_FILE = SCRAPPER_DIR / "summarized_web_search_results.txt"
    with open(SUMMARIZED_WEB_SEARCH_RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(result_summarized)

    return result_summarized


if __name__ == "__main__":
    search("Gustavo Bellanda")
