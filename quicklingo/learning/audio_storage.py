from __future__ import annotations

import re
from pathlib import Path

from quicklingo.paths import user_data_dir

AUDIO_PACK_SIZE = 50
CARD_AUDIO_ROOT = "card_audio"
PRONUNCIATIONS_ROOT = f"{CARD_AUDIO_ROOT}/pronunciations"
PACK_DIR_PATTERN = re.compile(r"^pack_(\d+)$")
_CARD_ID_RE = re.compile(r"^\d+$")

_pronunciation_migrated = False


def card_audio_root() -> Path:
    path = user_data_dir() / CARD_AUDIO_ROOT
    path.mkdir(parents=True, exist_ok=True)
    return path


def pronunciations_root() -> Path:
    path = card_audio_root() / "pronunciations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pack_dir_name(number: int) -> str:
    return f"pack_{number:06d}"


def _list_pack_dirs(root: Path) -> list[Path]:
    packs = [
        path
        for path in root.iterdir()
        if path.is_dir() and PACK_DIR_PATTERN.fullmatch(path.name)
    ]
    packs.sort(key=lambda path: int(PACK_DIR_PATTERN.fullmatch(path.name).group(1)))  # type: ignore[union-attr]
    return packs


def _count_mp3_files(pack_dir: Path) -> int:
    return sum(1 for path in pack_dir.glob("*.mp3") if path.is_file())


def _next_pack_number(root: Path) -> int:
    packs = _list_pack_dirs(root)
    if not packs:
        return 1
    last_name = packs[-1].name
    return int(PACK_DIR_PATTERN.fullmatch(last_name).group(1)) + 1  # type: ignore[union-attr]


def allocate_pack_file(root: Path, filename: str) -> Path:
    packs = _list_pack_dirs(root)
    if packs and _count_mp3_files(packs[-1]) < AUDIO_PACK_SIZE:
        return packs[-1] / filename
    pack_dir = root / pack_dir_name(_next_pack_number(root))
    pack_dir.mkdir(parents=True, exist_ok=True)
    return pack_dir / filename


def relative_path(path: Path) -> str:
    return path.relative_to(user_data_dir()).as_posix()


def allocate_pronunciation_path(card_id: int) -> Path:
    ensure_pronunciation_storage_migrated()
    return allocate_pack_file(pronunciations_root(), f"{card_id}.mp3")


def _move_file(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        source.unlink(missing_ok=True)
        return dest
    source.replace(dest)
    return dest


def _collect_pronunciation_sources() -> dict[int, Path]:
    root = card_audio_root()
    pron_root = pronunciations_root()
    sources: dict[int, Path] = {}

    def add_from_dir(directory: Path) -> None:
        if not directory.is_dir():
            return
        for mp3 in directory.glob("*.mp3"):
            if not mp3.is_file() or not _CARD_ID_RE.fullmatch(mp3.stem):
                continue
            sources[int(mp3.stem)] = mp3

    for path in root.iterdir():
        if path.is_dir() and path.name.isdigit():
            add_from_dir(path)
    for path in pron_root.iterdir():
        if path.is_dir() and path.name.isdigit():
            add_from_dir(path)
        elif path.is_dir() and PACK_DIR_PATTERN.fullmatch(path.name):
            add_from_dir(path)
    return sources


def ensure_pronunciation_storage_migrated() -> int:
    global _pronunciation_migrated
    if _pronunciation_migrated:
        return 0
    _pronunciation_migrated = True

    from quicklingo.db import learning

    sources = _collect_pronunciation_sources()
    if not sources:
        _cleanup_legacy_pronunciation_dirs()
        return 0

    pron_root = pronunciations_root()
    moved = 0
    for card_id in sorted(sources):
        source = sources[card_id]
        if (
            source.parent.parent == pron_root
            and PACK_DIR_PATTERN.fullmatch(source.parent.name)
            and _count_mp3_files(source.parent) <= AUDIO_PACK_SIZE
        ):
            rel = relative_path(source)
            card = learning.get_card(card_id)
            if card is not None and card.audio_path != rel:
                learning.update_card(card_id, audio_path=rel)
            continue

        dest = allocate_pack_file(pron_root, source.name)
        dest = _move_file(source, dest)
        rel = relative_path(dest)
        learning.update_card(card_id, audio_path=rel)
        moved += 1

    _cleanup_legacy_pronunciation_dirs()
    return moved


def _cleanup_legacy_pronunciation_dirs() -> None:
    root = card_audio_root()
    pron_root = pronunciations_root()
    for path in list(root.iterdir()):
        if path.is_dir() and path.name.isdigit():
            _remove_dir_if_empty(path)
    for path in list(pron_root.iterdir()):
        if path.is_dir() and path.name.isdigit():
            _remove_dir_if_empty(path)


def _remove_dir_if_empty(path: Path) -> None:
    if not path.is_dir():
        return
    if any(path.iterdir()):
        return
    path.rmdir()


def find_pronunciation_file(card_id: int) -> Path | None:
    ensure_pronunciation_storage_migrated()
    filename = f"{card_id}.mp3"
    for pack in _list_pack_dirs(pronunciations_root()):
        candidate = pack / filename
        if candidate.is_file():
            return candidate
    return None


def resolve_stored_pronunciation_path(stored_rel: str, *, card_id: int | None = None) -> Path | None:
    if stored_rel:
        path = user_data_dir() / stored_rel
        if path.is_file():
            return path
    if card_id is None:
        return None
    return find_pronunciation_file(card_id)
