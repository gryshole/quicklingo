from __future__ import annotations

import hashlib
import re
from pathlib import Path

from quicklingo.learning.pronunciation import _edge_tts_save
from quicklingo.learning.tts.text import prepare_text_for_tts
from quicklingo.paths import user_data_dir

_SENTENCE_SHARD_CHARS = 2
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_PACK_DIR_RE = re.compile(r"^pack_\d+$")
_legacy_migrated = False


def sentence_audio_dir() -> Path:
    path = user_data_dir() / "card_audio" / "sentences"
    path.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_sentence_cache(path)
    return path


def sentence_cache_digest(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def sentence_cache_shard(digest: str) -> str:
    return digest[:_SENTENCE_SHARD_CHARS]


def sentence_cache_path(text: str) -> Path:
    digest = sentence_cache_digest(text)
    shard_dir = sentence_audio_dir() / sentence_cache_shard(digest)
    shard_dir.mkdir(parents=True, exist_ok=True)
    return shard_dir / f"{digest}.mp3"


def _legacy_sentence_cache_path(text: str) -> Path:
    digest = sentence_cache_digest(text)
    return user_data_dir() / "card_audio" / "sentences" / f"{digest}.mp3"


def _shard_sentence_cache_path(digest: str) -> Path:
    root = user_data_dir() / "card_audio" / "sentences"
    shard_dir = root / sentence_cache_shard(digest)
    return shard_dir / f"{digest}.mp3"


def _move_sentence_file(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        source.unlink(missing_ok=True)
    else:
        source.replace(dest)


def _migrate_legacy_sentence_cache(base: Path | None = None) -> int:
    global _legacy_migrated
    if _legacy_migrated:
        return 0
    _legacy_migrated = True

    root = base or (user_data_dir() / "card_audio" / "sentences")
    if not root.is_dir():
        return 0

    moved = 0
    for path in list(root.iterdir()):
        if path.is_file() and path.suffix.lower() == ".mp3":
            if not _SHA256_HEX_RE.fullmatch(path.stem):
                continue
            dest = _shard_sentence_cache_path(path.stem)
            if path != dest:
                _move_sentence_file(path, dest)
                moved += 1
            continue
        if not path.is_dir() or path.name.startswith("_"):
            continue
        if _PACK_DIR_RE.fullmatch(path.name):
            for mp3 in list(path.glob("*.mp3")):
                if not _SHA256_HEX_RE.fullmatch(mp3.stem):
                    continue
                dest = _shard_sentence_cache_path(mp3.stem)
                if mp3 != dest:
                    _move_sentence_file(mp3, dest)
                    moved += 1
            if not any(path.iterdir()):
                path.rmdir()

    index_path = root / "_index.json"
    if index_path.is_file():
        index_path.unlink(missing_ok=True)

    return moved


def synthesize_sentence(text: str) -> Path | None:
    cleaned = prepare_text_for_tts(text)
    if not cleaned:
        return None
    output = sentence_cache_path(cleaned)
    if output.is_file():
        return output
    try:
        import asyncio
    except ImportError:
        return None
    try:
        asyncio.run(_edge_tts_save(cleaned, output))
    except Exception:
        return None
    return output if output.is_file() else None


def resolve_sentence_audio(text: str) -> Path | None:
    cleaned = prepare_text_for_tts(text)
    if not cleaned:
        return None
    path = sentence_cache_path(cleaned)
    if path.is_file():
        return path
    legacy = _legacy_sentence_cache_path(cleaned)
    if not legacy.is_file():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy.replace(path)
    return path
