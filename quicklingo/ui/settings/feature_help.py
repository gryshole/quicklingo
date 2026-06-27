from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from quicklingo.i18n import tr

_HOVER_MS = 1000
_MAX_WIDTH = 380
_GAP = 4

_active_bubble: FeatureHelpBubble | None = None


def help_key_for_feature(feature_key: str) -> str:
    slug = feature_key.replace(".", "_")
    return f"settings.features.help.{slug}"


def _hide_active_bubble() -> None:
    global _active_bubble
    if _active_bubble is not None:
        _active_bubble.hide()
        _active_bubble.deleteLater()
        _active_bubble = None


class FeatureHelpBubble(QFrame):
    _SHADOW_MARGIN = 8

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        m = self._SHADOW_MARGIN
        outer.setContentsMargins(m, m, m, m + 2)

        panel = QFrame()
        panel.setObjectName("FeatureHelpBubble")
        panel.setStyleSheet(
            """
            QFrame#FeatureHelpBubble {
                background: #ffffff;
                border: 1px solid #c8c8c8;
            }
            QLabel {
                color: #1a1a1a;
                background: transparent;
            }
            """
        )
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 70))
        panel.setGraphicsEffect(shadow)
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self._title = QLabel()
        title_font = self._title.font()
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._title.setWordWrap(True)
        self._title.setMaximumWidth(_MAX_WIDTH)

        self._body = QLabel()
        self._body.setWordWrap(True)
        self._body.setMaximumWidth(_MAX_WIDTH)

        layout.addWidget(self._title)
        layout.addWidget(self._body)
        self._panel = panel

    def set_content(self, title: str, body: str) -> None:
        self._title.setText(title)
        self._body.setText(body)
        self._title.setVisible(bool(title.strip()))

    def show_above(self, anchor: QWidget) -> None:
        self._panel.adjustSize()
        self.adjustSize()
        top_left = anchor.mapToGlobal(anchor.rect().topLeft())
        bottom_left = anchor.mapToGlobal(anchor.rect().bottomLeft())
        cursor_x = QCursor.pos().x()

        panel_w = self._panel.sizeHint().width()
        panel_h = self._panel.sizeHint().height()
        m = self._SHADOW_MARGIN
        width = panel_w + m * 2
        height = panel_h + m * 2 + 2

        # Align with the option row; prefer cursor X when still over the checkbox text.
        anchor_right = anchor.mapToGlobal(anchor.rect().topRight()).x()
        if top_left.x() <= cursor_x <= anchor_right:
            x = cursor_x - panel_w // 2 - m
        else:
            x = top_left.x() - m
        # Anchor the visible panel bottom just above the option row.
        y = top_left.y() - _GAP - m - panel_h

        screen = anchor.screen().availableGeometry()
        x = max(screen.left() + 4, min(x, screen.right() - width - 4))
        if y < screen.top() + 4:
            y = bottom_left.y() + _GAP

        self.setFixedSize(width, height)
        self.move(x, y)
        self.show()


class FeatureHelpFilter(QObject):
    def __init__(self, feature_key: str, title_key: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._feature_key = feature_key
        self._title_key = title_key
        self._hovering = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_HOVER_MS)
        self._timer.timeout.connect(self._show_help)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Enter:
            self._hovering = True
            self._timer.start()
        elif event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
            self._hovering = False
            self._timer.stop()
            _hide_active_bubble()
        return False

    def _show_help(self) -> None:
        if not self._hovering:
            return
        widget = self.parent()
        if not isinstance(widget, QWidget) or not widget.underMouse():
            return

        QToolTip.hideText()
        title = tr(self._title_key)
        body_key = help_key_for_feature(self._feature_key)
        body = tr(body_key)
        if body == body_key:
            body = tr("settings.features.help_missing")

        global _active_bubble
        _hide_active_bubble()
        bubble = FeatureHelpBubble()
        bubble.set_content(title, body)
        bubble.show_above(widget)
        _active_bubble = bubble


def attach_feature_help(checkbox: QCheckBox, feature_key: str, title_key: str) -> None:
    filt = FeatureHelpFilter(feature_key, title_key, checkbox)
    checkbox.installEventFilter(filt)
    checkbox.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    checkbox._feature_help_filter = filt  # keep reference
