from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

from quicklingo.paths import app_icon_path

_APP_ID = "gryshole.quicklingo.1"
_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def configure_windows_app_id(app_id: str | None = None) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id or _APP_ID)
    except (AttributeError, OSError):
        pass


def load_app_icon() -> QIcon | None:
    icon_path = app_icon_path()
    if not icon_path.is_file():
        return None

    source = QPixmap(str(icon_path))
    if source.isNull():
        return None

    side = min(source.width(), source.height())
    x = max(0, (source.width() - side) // 2)
    y = max(0, (source.height() - side) // 2)
    square = source.copy(x, y, side, side)

    icon = QIcon()
    for size in _ICON_SIZES:
        pixmap = square.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon.addPixmap(pixmap)
    return icon
