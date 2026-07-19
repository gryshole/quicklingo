from __future__ import annotations

import shiboken6
from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QCursor,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
)

from quicklingo.db import learning
from quicklingo.i18n import tr
from quicklingo.learning.quiz.aggregator import list_quiz_eligible_decks
from quicklingo.learning.quiz.deck_selection_prefs import load_play_deck_ids, save_play_deck_ids
from quicklingo.ui.app_theme import (
    BORDER_HOVER,
    CARD_BG,
    INPUT_BORDER,
    PRIMARY,
    RADIUS_CONTROL,
    TEXT_PRIMARY,
    _ensure_chevron_png,
    ensure_valid_point_font,
    settings_ui_font,
)

_ALL_ITEM_ID = -1
_DECK_ID_ROLE = Qt.ItemDataRole.UserRole
_INDICATOR_SIZE = 18
_ROW_HEIGHT = 36
_HPAD = 12
_LABEL_COLOR = "#0f172a"

_FIELD_STYLE = f"""
    QFrame#deckMultiSelectField {{
        background: {CARD_BG};
        border: 1px solid {INPUT_BORDER};
        border-radius: {RADIUS_CONTROL};
        min-height: 36px;
    }}
    QFrame#deckMultiSelectField:hover:!disabled {{
        border: 1px solid {BORDER_HOVER};
    }}
    QFrame#deckMultiSelectField[popupOpen="true"] {{
        border: 1px solid {PRIMARY};
    }}
    QFrame#deckMultiSelectField:disabled {{
        background: #f1f5f9;
        border-color: #e2e8f0;
    }}
"""

_POPUP_STYLE = f"""
    QFrame#deckMultiSelectPopup {{
        background: {CARD_BG};
        border: 1px solid {INPUT_BORDER};
        border-radius: {RADIUS_CONTROL};
    }}
    QFrame#deckMultiSelectPopup QListView {{
        border: none;
        background: transparent;
        outline: none;
        padding: 4px;
        color: {TEXT_PRIMARY};
    }}
"""


def _label_style(*, disabled: bool) -> str:
    color = "#94a3b8" if disabled else _LABEL_COLOR
    return f"color: {color}; background: transparent; border: none; padding: 0;"


class _CheckableListDelegate(QStyledItemDelegate):
    """Paint checkable rows with fixed-size boxes and a white checkmark."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = option.rect
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect.adjusted(2, 0, -2, 0), QColor("#f3f4f6"))

        check_state = Qt.CheckState.Unchecked
        raw = index.data(Qt.ItemDataRole.CheckStateRole)
        if raw is not None:
            check_state = Qt.CheckState(raw)

        box = QRect(
            rect.left() + _HPAD,
            rect.top() + (rect.height() - _INDICATOR_SIZE) // 2,
            _INDICATOR_SIZE,
            _INDICATOR_SIZE,
        )

        if check_state == Qt.CheckState.Checked:
            painter.setBrush(QColor("#3b82f6"))
            painter.setPen(QColor("#3b82f6"))
        else:
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QColor("#cbd5e1"))

        painter.drawRoundedRect(box, 4, 4)

        if check_state == Qt.CheckState.Checked:
            pen = QPen(QColor("#ffffff"), 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            cx, cy = box.x(), box.y()
            painter.drawLine(cx + 4, cy + 9, cx + 7, cy + 12)
            painter.drawLine(cx + 7, cy + 12, cx + 14, cy + 5)

        text_left = box.right() + 10
        text_rect = QRect(text_left, rect.top(), rect.right() - text_left - _HPAD, rect.height())
        painter.setPen(QColor("#374151"))
        text = index.data(Qt.ItemDataRole.DisplayRole)
        painter.setFont(option.font)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            str(text) if text is not None else "",
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(option.rect.width() if option.rect.width() > 0 else 340, _ROW_HEIGHT)


class CheckableComboBox(QFrame):
    """Multi-select deck picker with a popup list; avoids QComboBox toggle quirks."""

    selection_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_mode = True
        self._selected_ids: set[int] = set()
        self._updating = False
        self._display_text = ""
        self._suppress_open_on_release = False

        self.setObjectName("deckMultiSelectField")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(settings_ui_font())
        ensure_valid_point_font(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(4)

        self._label = QLabel()
        self._label.setObjectName("deckMultiSelectLabel")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._label.setFont(settings_ui_font())
        ensure_valid_point_font(self._label)
        layout.addWidget(self._label)

        self._arrow = QLabel()
        self._arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._arrow.setPixmap(QPixmap(str(_ensure_chevron_png())))
        self._arrow.setFixedSize(20, 20)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._arrow)

        self.setStyleSheet(_FIELD_STYLE)
        self.setProperty("popupOpen", "false")

        self._popup = QFrame(
            None,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self._popup.setObjectName("deckMultiSelectPopup")
        self._popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)

        self._list_view = QListView(self._popup)
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_view.setMinimumWidth(340)
        self._list_view.setUniformItemSizes(True)
        self._list_view.setFont(settings_ui_font())
        ensure_valid_point_font(self._list_view)
        self._list_view.setItemDelegate(_CheckableListDelegate(self._list_view))
        popup_layout.addWidget(self._list_view)

        self._popup.setStyleSheet(_POPUP_STYLE)

        self._model = QStandardItemModel(self)
        self._list_view.setModel(self._model)

        self._popup.installEventFilter(self)
        self._list_viewport = self._list_view.viewport()
        self._list_viewport.installEventFilter(self)

        self._restore_selection()
        self.reload_decks()

    def _qt_alive(self, obj) -> bool:
        return obj is not None and shiboken6.isValid(obj)

    def _detach_event_filters(self) -> None:
        popup = getattr(self, "_popup", None)
        viewport = getattr(self, "_list_viewport", None)
        if self._qt_alive(popup):
            popup.removeEventFilter(self)
            popup.hide()
        if self._qt_alive(viewport):
            viewport.removeEventFilter(self)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._detach_event_filters()
        super().closeEvent(event)

    def selected_deck_ids(self) -> frozenset[int] | None:
        if self._all_mode:
            return None
        return frozenset(self._selected_ids)

    def reload_decks(self) -> None:
        eligible = list_quiz_eligible_decks()
        eligible_ids = {deck.id for deck in eligible}
        if self._all_mode:
            self._selected_ids = set(eligible_ids)
        else:
            self._selected_ids &= eligible_ids
            if not self._selected_ids and eligible_ids:
                self._selected_ids = set(eligible_ids)
                self._all_mode = True
        self._rebuild_items(eligible)
        self.update_display_text()

    def retranslate_ui(self) -> None:
        self._rebuild_items(list_quiz_eligible_decks())
        self.update_display_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_label_elide()

    def _set_popup_open(self, open_state: bool) -> None:
        self.setProperty("popupOpen", "true" if open_state else "false")
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def _cursor_over_field(self) -> bool:
        return self.rect().contains(self.mapFromGlobal(QCursor.pos()))

    def _arm_close_on_release(self) -> None:
        self._suppress_open_on_release = True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.property("popupOpen") == "true" or (
                self._qt_alive(self._popup) and self._popup.isVisible()
            ):
                self._arm_close_on_release()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._suppress_open_on_release:
                self._suppress_open_on_release = False
                self._close_popup()
            elif self._qt_alive(self._popup) and not self._popup.isVisible():
                self._show_popup()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        try:
            popup = getattr(self, "_popup", None)
            list_view = getattr(self, "_list_view", None)
            viewport = getattr(self, "_list_viewport", None)

            if self._qt_alive(popup) and watched is popup and event.type() == QEvent.Type.Hide:
                if self._cursor_over_field():
                    self._arm_close_on_release()
                self._set_popup_open(False)

            if (
                self._qt_alive(list_view)
                and self._qt_alive(viewport)
                and watched is viewport
            ):
                if event.type() == QEvent.Type.MouseButtonRelease:
                    if event.button() != Qt.MouseButton.LeftButton:
                        return False
                    pos = (
                        event.position().toPoint()
                        if hasattr(event, "position")
                        else event.pos()
                    )
                    index = list_view.indexAt(pos)
                    if index.isValid():
                        self._handle_item_click(index)
                    return True
        except RuntimeError:
            return False
        return super().eventFilter(watched, event)

    def _close_popup(self) -> None:
        if not self._qt_alive(self._popup):
            return
        if self._popup.isVisible():
            self._popup.hide()
        self._set_popup_open(False)
        self.update_display_text()

    def _show_popup(self) -> None:
        row_count = max(1, self._model.rowCount())
        visible_rows = min(row_count, 12)
        popup_height = visible_rows * _ROW_HEIGHT + 12
        popup_width = max(self.width(), 340)
        self._popup.setFixedSize(popup_width, popup_height)
        anchor = self.mapToGlobal(QPoint(0, self.height() + 4))
        self._popup.move(anchor)
        self._set_popup_open(True)
        self._popup.show()
        self._list_view.setFocus()

    def _refresh_label_elide(self) -> None:
        if not self._display_text:
            return
        width = self._label.width()
        if width <= 0:
            self._label.setText(self._display_text)
            return
        metrics = QFontMetrics(self._label.font())
        self._label.setText(
            metrics.elidedText(self._display_text, Qt.TextElideMode.ElideRight, width)
        )

    def _apply_label_style(self) -> None:
        self._label.setStyleSheet(_label_style(disabled=not self.isEnabled()))

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self._apply_label_style()

    def update_display_text(self) -> None:
        deck_ids = self.selected_deck_ids()
        eligible = list_quiz_eligible_decks()
        if not eligible:
            text = tr("learning.quiz_decks_none")
        elif deck_ids is None:
            text = tr("learning.quiz_decks_all")
        elif not deck_ids:
            text = tr("learning.quiz_decks_none")
        elif len(deck_ids) == len(eligible):
            text = tr("learning.quiz_decks_all")
        elif len(deck_ids) == 1:
            deck_id = next(iter(deck_ids))
            deck = learning.get_deck(deck_id)
            text = deck.name if deck is not None else tr("learning.quiz_decks_none")
        else:
            text = tr("learning.quiz_decks_selected_count", count=len(deck_ids))

        self._display_text = text
        self._label.setToolTip(text)
        self._apply_label_style()
        self._refresh_label_elide()

    def _restore_selection(self) -> None:
        stored = load_play_deck_ids()
        if stored is None:
            self._all_mode = True
            self._selected_ids = set()
            return
        self._all_mode = False
        self._selected_ids = set(stored)

    @staticmethod
    def _make_checkable_item(text: str, deck_id: int) -> QStandardItem:
        item = QStandardItem(text)
        item.setData(deck_id, _DECK_ID_ROLE)
        item.setCheckable(True)
        item.setAutoTristate(False)
        item.setCheckState(Qt.CheckState.Unchecked)
        return item

    def _rebuild_items(self, decks: list[learning.LearningDeck]) -> None:
        self._updating = True
        self._model.clear()

        self._model.appendRow(self._make_checkable_item(tr("learning.quiz_decks_all"), _ALL_ITEM_ID))

        for deck in decks:
            stats = learning.get_quiz_coverage(deck.id)
            text = tr(
                "learning.quiz_deck_short_item",
                name=deck.name,
                ready=stats.ready,
                eligible=stats.eligible,
            )
            self._model.appendRow(self._make_checkable_item(text, deck.id))

        self._apply_check_states_to_model()
        self._updating = False

    def _apply_check_states_to_model(self) -> None:
        deck_total = self._model.rowCount() - 1

        for row in range(1, self._model.rowCount()):
            item = self._model.item(row)
            if item is None:
                continue
            deck_id = item.data(_DECK_ID_ROLE)
            checked = isinstance(deck_id, int) and deck_id in self._selected_ids
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

        all_item = self._model.item(0)
        if all_item is None:
            return

        checked_count = sum(
            1
            for row in range(1, self._model.rowCount())
            if self._model.item(row) is not None
            and self._model.item(row).checkState() == Qt.CheckState.Checked
        )
        if deck_total > 0 and checked_count == deck_total:
            all_item.setCheckState(Qt.CheckState.Checked)
        else:
            all_item.setCheckState(Qt.CheckState.Unchecked)

    def _set_all_items_check_state(self, state: Qt.CheckState) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item is not None:
                item.setCheckState(state)

    def _handle_item_click(self, index: QModelIndex) -> None:
        if self._updating or not index.isValid():
            return
        item = self._model.itemFromIndex(index)
        if item is None:
            return

        self._updating = True
        deck_id = item.data(_DECK_ID_ROLE)

        if deck_id == _ALL_ITEM_ID:
            deck_total = self._model.rowCount() - 1
            all_selected = self._all_mode or (
                deck_total > 0 and len(self._selected_ids) == deck_total
            )
            select_all = not all_selected
            if select_all:
                self._all_mode = True
                self._selected_ids = {
                    self._model.item(row).data(_DECK_ID_ROLE)
                    for row in range(1, self._model.rowCount())
                    if self._model.item(row) is not None
                }
                self._set_all_items_check_state(Qt.CheckState.Checked)
            else:
                self._all_mode = False
                self._selected_ids.clear()
                self._set_all_items_check_state(Qt.CheckState.Unchecked)
        else:
            if not isinstance(deck_id, int):
                self._updating = False
                return
            if deck_id in self._selected_ids:
                self._selected_ids.discard(deck_id)
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                self._selected_ids.add(deck_id)
                item.setCheckState(Qt.CheckState.Checked)

            deck_total = self._model.rowCount() - 1
            self._all_mode = deck_total > 0 and len(self._selected_ids) == deck_total
            self._apply_check_states_to_model()

        self._updating = False
        if self._qt_alive(self._list_viewport):
            self._list_viewport.update()
        self.update_display_text()
        self._emit_selection()

    def _emit_selection(self) -> None:
        deck_ids = self.selected_deck_ids()
        save_play_deck_ids(deck_ids)
        self.selection_changed.emit(deck_ids)


QuizDeckComboBox = CheckableComboBox
