import pprint
import re
import time

from duckpy import Client

client = Client()


def search(query: str) -> list[str]:
    """
    Search for a query on DuckDuckGo and return the URLs of the results.
    """
    start_time = time.perf_counter()
    results = client.search(query)
    end_time = time.perf_counter()
    print(f"🔍 DuckDuckGo searched for {query} in {end_time - start_time} seconds")

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
    pprint.pprint(results)
