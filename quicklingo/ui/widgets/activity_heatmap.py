from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from quicklingo.learning.analytics.models import DailyActivityDto

_CELL = 12
_CELL_GAP = 4
_WEEKS = 26
_DAYS = 7
_EMPTY = QColor("#D3D7DC")
_LEVELS = (
    QColor("#BBDEFB"),  # low
    QColor("#64B5F6"),  # medium-low
    QColor("#2196F3"),  # medium
    QColor("#0D47A1"),  # high
)


def _grid_size() -> tuple[int, int]:
    width = _WEEKS * (_CELL + _CELL_GAP) - _CELL_GAP
    height = _DAYS * (_CELL + _CELL_GAP) - _CELL_GAP
    return width, height


class ActivityHeatmapWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        grid_w, grid_h = _grid_size()
        self.setMinimumHeight(grid_h + 16)
        self.setMinimumWidth(grid_w + 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._counts: dict[date, int] = {}

    def set_activity(self, activity: list[DailyActivityDto]) -> None:
        self._counts = {item.day: item.count for item in activity}
        self.update()

    def _origin(self) -> tuple[int, int]:
        grid_w, grid_h = _grid_size()
        origin_x = max(0, (self.width() - grid_w) // 2)
        origin_y = max(0, (self.height() - grid_h) // 2)
        return origin_x, origin_y

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
        origin_x, origin_y = self._origin()
        step = _CELL + _CELL_GAP
        for week in range(_WEEKS):
            for weekday in range(_DAYS):
                day = start + timedelta(days=week * _DAYS + weekday)
                if day > today:
                    continue
                count = self._counts.get(day, 0)
                color = self._color_for(count, max_count=max_count)
                x = origin_x + week * step
                y = origin_y + weekday * step
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
        origin_x, origin_y = self._origin()
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

    def sizeHint(self) -> QSize:
        grid_w, grid_h = _grid_size()
        return QSize(grid_w + 8, grid_h + 8)
