from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from quicklingo.paths import user_data_dir

_WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"


def card_image_dir(deck_id: int) -> Path:
    path = user_data_dir() / "card_images" / str(deck_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_image_path(relative: str) -> Path | None:
    if not relative:
        return None
    path = user_data_dir() / relative
    return path if path.is_file() else None


def fetch_card_image(
    deck_id: int,
    card_id: int,
    *,
    prompt: str,
    search_term: str = "",
) -> str | None:
    """Return relative image_path or None."""
    query = (search_term or prompt).strip()
    if not query:
        return None
    image_bytes = _search_wikimedia(query)
    if not image_bytes:
        return None
    output = card_image_dir(deck_id) / f"{card_id}.webp"
    try:
        output.write_bytes(image_bytes)
    except OSError:
        return None
    return output.relative_to(user_data_dir()).as_posix()


def _search_wikimedia(query: str) -> bytes | None:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": "5",
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": "512",
    }
    try:
        with httpx.Client(timeout=20.0, headers={"User-Agent": "QuickLingo/1.0"}) as client:
            response = client.get(_WIKIMEDIA_API, params=params)
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                imageinfo = page.get("imageinfo") or []
                if not imageinfo:
                    continue
                thumb = imageinfo[0].get("thumburl") or imageinfo[0].get("url")
                if not thumb:
                    continue
                image_response = client.get(thumb)
                image_response.raise_for_status()
                return image_response.content
    except httpx.HTTPError:
        return None
    return None
