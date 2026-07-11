from __future__ import annotations

import logging
from pathlib import Path

import httpx

from quicklingo import settings
from quicklingo.paths import user_data_dir
from quicklingo.version import __version__

_PIXABAY_API = "https://pixabay.com/api/"
_USER_AGENT = f"QuickLingo/{__version__}"
_MAX_QUERY_LEN = 100

_logger = logging.getLogger("quicklingo.card_images")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("card_images: %(levelname)s: %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


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
    """Download a Pixabay photo and return relative image_path, or None."""
    api_key = settings.get_api_key("pixabay").strip()
    if not api_key:
        _logger.warning("card %s: Pixabay API key is not set", card_id)
        return None

    query = _build_query(prompt=prompt, search_term=search_term)
    if not query:
        _logger.info("card %s: empty search query", card_id)
        return None

    found = _search_pixabay(api_key, query)
    if not found:
        return None
    image_bytes, extension = found

    output = card_image_dir(deck_id) / f"{card_id}.{extension}"
    for stale in card_image_dir(deck_id).glob(f"{card_id}.*"):
        if stale != output:
            try:
                stale.unlink(missing_ok=True)
            except OSError:
                pass
    try:
        output.write_bytes(image_bytes)
    except OSError as exc:
        _logger.warning("card %s: failed to write %s: %s", card_id, output, exc)
        return None
    _logger.info("card %s: saved Pixabay photo for query %r", card_id, query)
    return output.relative_to(user_data_dir()).as_posix()


def _build_query(*, prompt: str, search_term: str) -> str:
    """Build a short Pixabay query.

    Full AI scene prompts ("A red apple on a white background") rank poorly on
    Pixabay — filler words like "white" / "background" dominate. Prefer the
    card front term, then a short noun phrase from the prompt.
    """
    term = " ".join((search_term or "").split()).strip()
    if term:
        return term[:_MAX_QUERY_LEN].rstrip()

    # Fallback when front is empty: keep only a few content words from prompt.
    stop = {
        "a",
        "an",
        "the",
        "on",
        "in",
        "of",
        "and",
        "or",
        "with",
        "for",
        "to",
        "from",
        "at",
        "by",
        "as",
        "is",
        "are",
        "white",
        "black",
        "background",
        "simple",
        "photo",
        "image",
        "picture",
        "illustration",
        "drawing",
        "scene",
        "showing",
        "against",
    }
    tokens = [
        t.strip(".,;:!?\"'()[]")
        for t in (prompt or "").replace(",", " ").split()
    ]
    meaningful = [t for t in tokens if t and t.casefold() not in stop and len(t) > 1]
    if not meaningful:
        text = " ".join((prompt or "").split()).strip()
        return text[:_MAX_QUERY_LEN].rstrip()
    # Keep a short phrase (e.g. "red apple"), not the whole scene sentence.
    text = " ".join(meaningful[:3])
    return text[:_MAX_QUERY_LEN].rstrip()


def _sniff_extension(data: bytes, content_type: str = "") -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct:
        return "jpg"
    if "png" in ct:
        return "png"
    if "gif" in ct:
        return "gif"
    if "webp" in ct:
        return "webp"
    return "jpg"


def _search_pixabay(api_key: str, query: str) -> tuple[bytes, str] | None:
    params = {
        "key": api_key,
        "q": query,
        "image_type": "photo",
        "per_page": "3",
        "safesearch": "true",
        "page": "1",
    }
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
            response = client.get(_PIXABAY_API, params=params)
            if response.status_code >= 400:
                _logger.warning(
                    "Pixabay search HTTP %s for %r: %s",
                    response.status_code,
                    query,
                    response.text[:200],
                )
                return None
            data = response.json()
            hits = data.get("hits") or []
            if not hits:
                _logger.warning("Pixabay empty result for %r", query)
                return None
            url = str(hits[0].get("webformatURL") or "").strip()
            if not url:
                _logger.warning("Pixabay hit missing webformatURL for %r", query)
                return None
            image_response = client.get(url)
            if image_response.status_code >= 400:
                _logger.warning(
                    "Pixabay image HTTP %s for %s",
                    image_response.status_code,
                    url,
                )
                return None
            payload = image_response.content
            if not payload:
                return None
            ext = _sniff_extension(
                payload, image_response.headers.get("content-type", "")
            )
            return payload, ext
    except httpx.HTTPError as exc:
        _logger.warning("Pixabay request failed for %r: %s", query, exc)
        return None
    except ValueError as exc:
        _logger.warning("Pixabay JSON parse failed for %r: %s", query, exc)
        return None
