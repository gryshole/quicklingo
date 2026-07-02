from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from quicklingo.learning.analytics.models import DailyActivityDto

_CELL = 11
_CELL_GAP = 3
_WEEKS = 26
_DAYS = 7
_EMPTY = QColor("#f1f5f9")
_LEVELS = (
    QColor("#dbeafe"),
    QColor("#93c5fd"),
    QColor("#3b82f6"),
    QColor("#2563eb"),
)


class ActivityHeatmapWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._counts: dict[date, int] = {}
        self.setMinimumHeight(_DAYS * (_CELL + _CELL_GAP) + 24)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_activity(self, activity: list[DailyActivityDto]) -> None:
        self._counts = {item.day: item.count for item in activity}
        self.update()

    def _color_for(self, count: int, *, max_count: int) -> QColor:
        if count <= 0:
            return _EMPTY
        if max_count <= 0:
            return _LEVELS[0]
        ratio = count / max_count
        if ratio <= 0.25:
            return _LEVELS[0]
        if ratio <= 0.5:
            return _LEVELS[1]
        if ratio <= 0.75:
            return _LEVELS[2]
        return _LEVELS[3]

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        today = date.today()
        start = today - timedelta(days=_WEEKS * _DAYS - 1)
        max_count = max(self._counts.values(), default=0)
        origin_x = 4
        origin_y = 4
        for week in range(_WEEKS):
            for weekday in range(_DAYS):
                day = start + timedelta(days=week * _DAYS + weekday)
                if day > today:
                    continue
                count = self._counts.get(day, 0)
                color = self._color_for(count, max_count=max_count)
                x = origin_x + week * (_CELL + _CELL_GAP)
                y = origin_y + weekday * (_CELL + _CELL_GAP)
                rect = QRectF(x, y, _CELL, _CELL)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(rect, 2, 2)

    def mouseMoveEvent(self, event) -> None:
        cell = self._cell_at(event.position().x(), event.position().y())
        if cell is None:
            QToolTip.hideText()
            super().mouseMoveEvent(event)
            return
        day, count = cell
        QToolTip.showText(
            event.globalPosition().toPoint(),
            f"{day.isoformat()} · {count}",
            self,
        )
        super().mouseMoveEvent(event)

    def leaveEvent(self, _event) -> None:
        QToolTip.hideText()
        super().leaveEvent(_event)

    def _cell_at(self, x: float, y: float) -> tuple[date, int] | None:
        origin_x = 4
        origin_y = 4
        step = _CELL + _CELL_GAP
        week = int((x - origin_x) // step)
        weekday = int((y - origin_y) // step)
        if week < 0 or week >= _WEEKS or weekday < 0 or weekday >= _DAYS:
            return None
        if (x - origin_x) % step > _CELL or (y - origin_y) % step > _CELL:
            return None
        today = date.today()
        start = today - timedelta(days=_WEEKS * _DAYS - 1)
        day = start + timedelta(days=week * _DAYS + weekday)
        if day > today:
            return None
        return day, self._counts.get(day, 0)

    def sizeHint(self):
        from PySide6.QtCore import QSize

        width = _WEEKS * (_CELL + _CELL_GAP) + 8
        height = _DAYS * (_CELL + _CELL_GAP) + 8
        return QSize(width, height)
