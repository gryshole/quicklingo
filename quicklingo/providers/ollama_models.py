from __future__ import annotations

import httpx

from quicklingo import settings

OLLAMA_TAGS_TIMEOUT = 2.0


def fetch_ollama_model_ids() -> list[str]:
    base = settings.get_ollama_base_url().rstrip("/")
    root = base[:-3] if base.endswith("/v1") else base
    url = f"{root}/api/tags"
    try:
        response = httpx.get(url, timeout=OLLAMA_TAGS_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return []
    models = data.get("models")
    if not isinstance(models, list):
        return []
    ids: list[str] = []
    for item in models:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                ids.append(name.strip())
    return ids
