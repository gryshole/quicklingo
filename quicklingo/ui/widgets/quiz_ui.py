"""Shared quiz UI helpers (icons, small formatters)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap

from quicklingo.paths import resource_path

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "quiz"
_ICON_SIZE_DEFAULT = 24
# Inset so stroke icons are not clipped at the SVG viewBox edge.
_SVG_RENDER_INSET_RATIO = 0.12


def _device_pixel_ratio() -> float:
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen()
    if screen is None:
        return 1.0
    return float(screen.devicePixelRatio())


def _icon_from_pixmap(pixmap: QPixmap) -> QIcon:
    icon = QIcon()
    for mode in (
        QIcon.Mode.Normal,
        QIcon.Mode.Disabled,
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
    ):
        icon.addPixmap(pixmap, mode, QIcon.State.Off)
    return icon


def _render_svg(renderer, size: int, *, vertical_nudge: float = 0.0) -> QIcon:
    dpr = _device_pixel_ratio()
    physical = max(1, round(size * dpr))
    inset = physical * _SVG_RENDER_INSET_RATIO
    y = inset + physical * vertical_nudge
    target = QRectF(inset, y, physical - 2 * inset, physical - 2 * inset)

    pixmap = QPixmap(physical, physical)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(dpr)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, target)
    painter.end()
    return _icon_from_pixmap(pixmap)


def _svg_icon(
    inner_svg: str,
    *,
    size: int = _ICON_SIZE_DEFAULT,
    color: str = "#2563eb",
    stroke_width: float = 2.5,
    vertical_nudge: float = 0.0,
) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{inner_svg}</svg>"
    )
    try:
        from PySide6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(svg.encode("utf-8"))
        if not renderer.isValid():
            return QIcon()
        return _render_svg(renderer, size, vertical_nudge=vertical_nudge)
    except Exception:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        return _icon_from_pixmap(pixmap)


def _icon_from_svg_file(path: Path, size: int, *, vertical_nudge: float = 0.0) -> QIcon:
    try:
        from PySide6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(str(path.resolve()))
        if not renderer.isValid():
            return QIcon()
        return _render_svg(renderer, size, vertical_nudge=vertical_nudge)
    except Exception:
        return QIcon()


def _asset_icon(name: str, size: int = _ICON_SIZE_DEFAULT, *, vertical_nudge: float = 0.0) -> QIcon:
    for candidate in (
        _ASSETS / name,
        resource_path(f"quicklingo/ui/assets/quiz/{name}"),
    ):
        if candidate.is_file():
            icon = _icon_from_svg_file(candidate, size, vertical_nudge=vertical_nudge)
            if not icon.isNull():
                return icon
    return QIcon()


def speaker_icon(*, size: int = 18, color: str = "#2563eb") -> QIcon:
    icon = _asset_icon("speaker.svg", size=size)
    if not icon.isNull():
        return icon
    return _svg_icon(
        '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>'
        '<path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>'
        '<path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
        size=size,
        color=color,
        stroke_width=2,
    )


def check_icon(*, size: int = _ICON_SIZE_DEFAULT, color: str = "#22c55e") -> QIcon:
    return _svg_icon(
        '<path d="M20 6 9 17l-5-5"/>',
        size=size,
        color=color,
        stroke_width=3.25,
        vertical_nudge=0.02,
    )


def x_icon(*, size: int = _ICON_SIZE_DEFAULT, color: str = "#ef4444") -> QIcon:
    return _svg_icon(
        '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
        size=size,
        color=color,
        stroke_width=3.25,
        vertical_nudge=0.02,
    )


def arrow_right_icon(*, size: int = _ICON_SIZE_DEFAULT, color: str = "#ffffff") -> QIcon:
    icon = _asset_icon("arrow_right.svg", size=size)
    if not icon.isNull():
        return icon
    return _svg_icon(
        '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
        size=size,
        color=color,
    )


EXAMPLE_SPEAKER_GHOST_STYLE = """
    QPushButton#quizExampleSpeakerBtn {
        background: transparent;
        border: none;
        border-radius: 14px;
        min-width: 28px;
        min-height: 28px;
        max-width: 28px;
        max-height: 28px;
        padding: 0;
    }
    QPushButton#quizExampleSpeakerBtn:hover {
        background: #f1f5f9;
    }
    QPushButton#quizExampleSpeakerBtn:pressed {
        background: #e2e8f0;
    }
"""

PROMPT_SPEAKER_BUTTON_STYLE = """
    QPushButton#quizSpeakerBtn {
        background: #eff6ff;
        border: none;
        border-radius: 18px;
        min-width: 36px;
        min-height: 36px;
        max-width: 36px;
        max-height: 36px;
        padding: 0;
    }
    QPushButton#quizSpeakerBtn:hover {
        background: #dbeafe;
    }
    QPushButton#quizSpeakerBtn:pressed {
        background: #bfdbfe;
    }
"""


def quiz_term_highlight_style() -> str:
    return "font-weight:700;color:#15803d;"
