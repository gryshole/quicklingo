import os
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        base = Path(app_data) / "QuickLingo"
    else:
        base = Path.home() / ".quicklingo"
    base.mkdir(parents=True, exist_ok=True)
    return base
