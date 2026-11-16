import time
from urllib.parse import parse_qs, urlparse

import structlog
from bs4 import BeautifulSoup
from curl_cffi import requests

log = structlog.get_logger(__name__)

# Decision 2026-11-15 (wave U5): duckpy 3.x was dropped. It calls httpx.Client(proxies=...) (removed
# in httpx 0.28) and pulls httpx, which the fleet replaced by curl_cffi. This module keeps the same
# contract (list of {url, title, description}) on the same HTML endpoint, parsed with bs4.
DDG_HTML_URL = "https://html.duckduckgo.com/html"
MAX_RESULTS = 10
REQUEST_TIMEOUT_SECONDS = 15


def _clean_url(href: str) -> str:
    """DuckDuckGo wraps result links as //duckduckgo.com/l/?uddg=<encoded>&rut=...; unwrap to the target."""
    wrapped = parse_qs(urlparse(href).query).get("uddg")
    return wrapped[0] if wrapped else href


def parse_results(html: str | bytes) -> list[dict]:
    """Parse the DuckDuckGo HTML results page, skipping ads and malformed blocks."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for block in soup.find_all("div", {"class": "links_main"}):
        if block.find("a", {"class": "badge--ad"}):
            continue
        title_a = block.h2.a if block.h2 else None
        snippet_a = block.find("a", {"class": "result__snippet"})
        url_a = block.find("a", {"class": "result__url"})
        if not (title_a and snippet_a and url_a and url_a.get("href")):
            continue
        results.append(
            {
                "url": _clean_url(url_a["href"]),
                "title": title_a.text.strip(),
                "description": snippet_a.text.strip(),
            }
        )
    return results


def search(query: str) -> list[dict]:
    """
    Search for a query on DuckDuckGo and return the top results (url, title, description).
    """
    start_time = time.perf_counter()
    response = requests.post(
        DDG_HTML_URL,
        data={"q": query},
        impersonate="chrome",
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = parse_results(response.content)[:MAX_RESULTS]
    end_time = time.perf_counter()
    log.info("duckduckgo_searched", query=query, seconds=end_time - start_time)
    return results


if __name__ == "__main__":
    results = search("Gustavo Bellanda")
    log.info("duckduckgo_results", results=results)
