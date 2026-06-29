from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from quicklingo.version import __repo__, __version__

_GITHUB_API = f"https://api.github.com/repos/{__repo__}/releases/latest"
_ASSET_PATTERN = re.compile(r"^QuickLingo-.*-win64\.zip$", re.IGNORECASE)
_DOWNLOAD_TIMEOUT = 120
_API_TIMEOUT = 15


@dataclass(frozen=True)
class UpdateInfo:
    latest_version: str
    release_url: str
    download_url: str
    release_notes: str


def parse_version(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lstrip("vV")
    parts: list[int] = []
    for piece in cleaned.split("."):
        if not piece.isdigit():
            raise ValueError(f"Invalid version segment: {piece!r}")
        parts.append(int(piece))
    if not parts:
        raise ValueError(f"Invalid version: {version!r}")
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def current_version() -> str:
    return __version__


def _request_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"QuickLingo/{__version__}",
        },
    )
    with urllib.request.urlopen(request, timeout=_API_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _pick_asset(assets: list[dict]) -> dict | None:
    for asset in assets:
        name = asset.get("name", "")
        if _ASSET_PATTERN.match(name):
            return asset
    for asset in assets:
        name = asset.get("name", "")
        if name.lower().endswith(".zip"):
            return asset
    return None


def fetch_latest() -> UpdateInfo:
    data = _request_json(_GITHUB_API)
    tag_name = str(data.get("tag_name", "")).lstrip("vV")
    if not tag_name:
        raise ValueError("Release has no tag_name")

    asset = _pick_asset(data.get("assets") or [])
    if asset is None:
        raise ValueError("Release has no Windows zip asset")

    download_url = str(asset.get("browser_download_url") or "")
    if not download_url:
        raise ValueError("Release asset has no download URL")

    return UpdateInfo(
        latest_version=tag_name,
        release_url=str(data.get("html_url") or ""),
        download_url=download_url,
        release_notes=str(data.get("body") or ""),
    )


def download_release(
    info: UpdateInfo,
    dest: Path,
    progress_cb: Callable[[int, int | None], None] | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        info.download_url,
        headers={"User-Agent": f"QuickLingo/{__version__}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT) as response:
            total_raw = response.headers.get("Content-Length")
            total = int(total_raw) if total_raw else None
            downloaded = 0
            chunk_size = 256 * 1024
            with dest.open("wb") as handle:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb is not None:
                        progress_cb(downloaded, total)
    except urllib.error.URLError as exc:
        if dest.is_file():
            dest.unlink(missing_ok=True)
        raise exc
    return dest


def default_download_path(version: str) -> Path:
    from quicklingo.paths import user_data_dir

    return user_data_dir() / "updates" / f"QuickLingo-{version}-win64.zip"
