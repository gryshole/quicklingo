from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap

from quicklingo.ui.widgets.review_session_theme import IMAGE_RADIUS, IMAGE_SIZE


def get_rounded_pixmap(
    pixmap: QPixmap,
    *,
    size: int = IMAGE_SIZE,
    radius: int = IMAGE_RADIUS,
) -> QPixmap:
    """Scale-to-fill square crop, then clip to rounded corners (QSS cannot do this)."""
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    cropped = scaled.copy(x, y, size, size)
    target = QPixmap(cropped.size())
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, cropped.width(), cropped.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return target


def html_definition_block(body_html: str) -> str:
    return (
        '<table cellspacing="0" cellpadding="0" border="0" '
        'style="margin:0;border-collapse:separate;">'
        "<tr>"
        '<td style="background-color:#F8FAFC;border:1px solid #E2E8F0;'
        "border-radius:8px;padding:10px 14px;color:#475569;font-size:15px;"
        'white-space:normal;word-wrap:break-word;">'
        f"<b>Definition:</b> <i>{body_html}</i>"
        "</td></tr></table>"
    )


def definition_body_from_notes(notes: str) -> str:
    plain = (notes or "").strip()
    if plain.lower().startswith("definition:"):
        plain = plain.split(":", 1)[1].strip()
    return plain
