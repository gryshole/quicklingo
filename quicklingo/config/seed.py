from __future__ import annotations

import shutil
from pathlib import Path

from quicklingo.paths import default_config_dir, user_config_dir


def _config_dir_is_empty(path: Path) -> bool:
    if not path.is_dir():
        return True
    return not any(path.rglob("*"))


def ensure_user_config() -> None:
    """Copy distribution config into APPDATA when the user config folder is empty."""
    target = user_config_dir()
    if not _config_dir_is_empty(target):
        return

    source = default_config_dir()
    if not source.is_dir():
        raise FileNotFoundError(
            f"Distribution config not found: {source}. "
            "Place config_data next to QuickLingo.exe."
        )

    for src_path in source.rglob("*"):
        rel = src_path.relative_to(source)
        dest_path = target / rel
        if src_path.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
