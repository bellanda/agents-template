import re
import time

import structlog
from duckpy import Client

log = structlog.get_logger(__name__)

client = Client()


def search(query: str) -> list[str]:
    """
    Search for a query on DuckDuckGo and return the URLs of the results.
    """
    start_time = time.perf_counter()
    results = client.search(query)
    end_time = time.perf_counter()
    log.info("duckduckgo_searched", query=query, seconds=end_time - start_time)

    return [
        {
            "url": re.findall(r"m/l/\?uddg=(.*)&rut", result["url"])[0],
            "title": result["title"],
            "description": result["description"],
        }
        for result in results[0:10]
    ]


if __name__ == "__main__":
    results = search("Gustavo Bellanda")
    log.info("duckduckgo_results", results=results)
