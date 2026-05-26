---
name: http-client
description: curl_cffi HTTP client patterns — TLS fingerprinting, async sessions, JSON handling. Use when making HTTP calls from Python backends, integrating external APIs, or replacing requests/httpx.
---

# HTTP Client — curl_cffi

Replaces `requests` and `httpx` across the Python stack. Built on libcurl with HTTP/3 and browser TLS fingerprinting. Covers sync, async (FastAPI), error handling, and session patterns.

## Sync Usage

```python
from curl_cffi import requests as curl_requests

# Basic GET with Chrome TLS fingerprint
response = curl_requests.get(
    "https://api.example.com/data",
    impersonate="chrome",
    headers={"Authorization": "Bearer token"},
)
response.raise_for_status()
data = response.json()

# POST with JSON body
response = curl_requests.post(
    "https://api.example.com/items",
    impersonate="chrome",
    json={"name": "item", "value": 42},
)
```

## Async Usage (FastAPI Integration)

```python
from curl_cffi.requests import AsyncSession

async def fetch_external_data(url: str) -> dict:
    async with AsyncSession(impersonate="chrome") as session:
        response = await session.get(url)
        response.raise_for_status()
        return response.json()

# Reusable session for multiple requests
async def fetch_multiple_pages(base_url: str, page_count: int) -> list[dict]:
    results = []
    async with AsyncSession(impersonate="chrome") as session:
        for page in range(1, page_count + 1):
            response = await session.get(f"{base_url}?page={page}")
            response.raise_for_status()
            results.append(response.json())
    return results
```

## Key Options

| Option            | Purpose                   | Example                             |
| ----------------- | ------------------------- | ----------------------------------- |
| `impersonate`     | TLS fingerprint           | `"chrome"`, `"firefox"`, `"safari"` |
| `timeout`         | Request timeout (seconds) | `timeout=30`                        |
| `proxies`         | Proxy configuration       | `{"https": "socks5://..."}`         |
| `verify`          | SSL verification          | `verify=False` (only for dev)       |
| `allow_redirects` | Follow redirects          | `allow_redirects=True` (default)    |

## Notes

- Always use `impersonate="chrome"` for external APIs to avoid bot detection.
- Use `AsyncSession` in FastAPI — never sync requests in async context.
- `response.json()` returns parsed dict directly.
- `response.raise_for_status()` raises `curl_cffi.requests.errors.RequestsError` on 4xx/5xx.
