import re
import time

import requests
from bs4 import BeautifulSoup

from api.utils.tools import generate_error_message, generate_result_message


def scrape_url(url: str) -> str:
    """Scrape content from a single URL."""
    start_time = time.time()

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text content
        text = soup.get_text()

        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)

        end_time = time.time()
        success_msg = generate_result_message("success", f"Scraped {url} in {end_time - start_time:.2f}s")
        print(f"🔍 {success_msg}")

        return text

    except Exception as e:
        end_time = time.time()
        error_msg = generate_error_message(f"Failed to scrape {url} in {end_time - start_time:.2f}s: {str(e)}")
        print(f"❌ {error_msg}")
        return ""


def perform_scraping(url: str) -> str:
    """Legacy function for backward compatibility."""
    start_time = time.time()

    try:
        content = scrape_url(url)
        if content:
            return content
        else:
            return f"ERRO_SCRAPING: Não foi possível extrair conteúdo de {url}"

    except Exception as e:
        end_time = time.time()
        error_msg = generate_error_message(f"Error parsing {url} in {end_time - start_time:.2f}s: {str(e)}")
        print(f"❌ {error_msg}")
        return f"ERRO_EXCEPTION: {str(e)}"


def smart_strip(text: str) -> str:
    """
    Remove espaços e quebras de linha excessivos, mantendo formatação legível.
    - Reduz múltiplos espaços para no máximo 2
    - Reduz múltiplas quebras de linha para no máximo 3
    - Remove espaços no início e fim de cada linha
    """
    # Remove espaços no início e fim
    text = text.strip()

    # Substitui múltiplos espaços (6 ou mais) por 2 espaços
    text = re.sub(r" {6,}", "  ", text)

    # Substitui múltiplos espaços (3-5) por 1 espaço
    text = re.sub(r" {3,5}", " ", text)

    # Remove espaços no início e fim de cada linha
    lines = text.split("\n")
    lines = [line.strip() for line in lines]
    text = "\n".join(lines)

    # Substitui múltiplas quebras de linha (5 ou mais) por 3
    text = re.sub(r"\n{5,}", "\n\n\n", text)

    # Substitui múltiplas quebras de linha (4) por 2
    text = re.sub(r"\n{4}", "\n\n", text)

    return text


if __name__ == "__main__":
    import pathlib
    import sys

    sys.path.append("/home/bellanda/code/projects-templates/agents-template")

    current_dir = pathlib.Path(__file__).parent

    from llms.groq import call_groq_llm

    result = perform_scraping("https://bellanda.github.io/dev/")
    with open(current_dir / "result.txt", "w", encoding="utf-8") as f:
        f.write(result)

    prompt = f"""
        Você é um analista de conteúdos da web especializado em condensar grandes volumes de texto.

        ## Objetivo
        Receber **exatamente 5** páginas completas — cada uma no formato:

        ### <Título da Página N>
        <corpo completo da Página N>

        e devolver **uma resposta única** que:
        1. Contêm todas as informações essenciais (fatos, números, datas, nomes, conclusões).
        2. Elimina repetições e detalhes triviais (ex.: código, anúncios, botões).
        3. Resolva possíveis contradições ou indique divergências, se houver.
        4. Já esteja pronta para ser lida por um agente-chamador (não precisa de pós-processamento).

        ## Passos internos (Chain-of-Thought oculto)
        1. **Para cada página**: extraia
        • Tópicos centrais  
        • Dados quantitativos e citações relevantes  
        • Conclusão ou take-away principal
        2. **Agrupe** tópicos semelhantes das cinco páginas e integre informações complementares.
        3. **Detecte incoerências**: se dois textos divergem, aponte brevemente (“Fonte A diz X, Fonte B diz Y”).
        4. **Monte o resumo final** (veja formato abaixo).

        ## Formato de saída (exporte apenas o texto abaixo)
        **Resumo Integrado (≤ 250 palavras)**  
        Um parágrafo ou lista curta que responda de forma direta ao tema comum das páginas.

        **Principais Pontos Organizados**
        - *Tópico 1*: frase-síntese + dados / exemplos
        - *Tópico 2*: …
        *(Use no máx. 7 bullets.)*

        **Notas de Divergência (opcional)**
        - Se houver conflito: “Página 1 vs Página 3: …”

        **Mapa de Origem**
        Título da Página 1 → [ideia-chave-1, ideia-chave-2]  
        Título da Página 2 → …  
        *(Cite apenas as ideias condensadas — não copie texto literal.)*

        ## Regras
        - Escreva em **português claro e conciso**.
        - Não invente informações; baseie-se apenas no texto recebido.
        - Não inclua explicações sobre seu raciocínio.
        - Não formate como código nem rode markdown excessivo (use headings e bullets simples).
        - Se faltar uma das 5 páginas, mencione: “Aviso: página X ausente”.

        (Conteúdo fornecido começa abaixo.)
        {result}
    """

    with open(current_dir / "result_summarized.txt", "w", encoding="utf-8") as f:
        f.write(call_groq_llm("llama3-8b-8192", prompt, max_tokens=1024))
