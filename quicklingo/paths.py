import os
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", app_root()))
        return base / relative
    return app_root() / relative


def user_data_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        base = Path(app_data) / "QuickLingo"
    else:
        base = Path.home() / ".quicklingo"
    base.mkdir(parents=True, exist_ok=True)
    return base


def user_config_dir() -> Path:
    path = user_data_dir() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_config_dir() -> Path:
    return app_root() / "config_data"


def app_icon_path() -> Path:
    ui_icon = resource_path("assets/quicklingo_icon_ui.png")
    if ui_icon.is_file():
        return ui_icon
    return resource_path("assets/quicklingo_icon.png")
