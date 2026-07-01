from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_dir(base: Path, subdir: str) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    directory = base / subdir
    if not directory.is_dir():
        return items
    for path in sorted(directory.glob("*.json")):
        data = read_json(path)
        item_id = data.get("id") or path.stem
        items[item_id] = data
    return items
