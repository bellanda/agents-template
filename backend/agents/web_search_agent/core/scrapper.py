import asyncio
import re
import time

from bs4 import BeautifulSoup
from curl_cffi import requests

from api.services.agents.tools import generate_error_message, generate_result_message


def _scrape_url_sync(url: str) -> str:
    """Synchronous scraping function to be run in thread."""
    start_time = time.time()

    try:
        response = requests.get(url, timeout=5, impersonate="chrome")
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


async def scrape_url(url: str) -> str:
    """Scrape content from a single URL asynchronously."""
    return await asyncio.to_thread(_scrape_url_sync, url)


async def perform_scraping(url: str) -> str:
    """Legacy function for backward compatibility."""
    start_time = time.time()

    try:
        content = await scrape_url(url)
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
    print(_scrape_url_sync("https://br.linkedin.com/in/arnando-teixeira-silva-filho-613155240"))
