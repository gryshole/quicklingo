from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal, QModelIndex, QRect, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QLineEdit,
    QListView,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
)

from quicklingo.db import learning
from quicklingo.i18n import tr
from quicklingo.learning.quiz.aggregator import list_quiz_eligible_decks
from quicklingo.learning.quiz.deck_selection_prefs import load_play_deck_ids, save_play_deck_ids

_ALL_ITEM_ID = -1
_DECK_ID_ROLE = Qt.ItemDataRole.UserRole
_INDICATOR_SIZE = 18
_ROW_HEIGHT = 36
_HPAD = 12

_COMBO_STYLE = """
    QComboBox {
        border: 1px solid #d1d5db;
        border-radius: 8px;
        padding: 8px 12px;
        background-color: white;
        color: #1f2937;
    }
    QComboBox:hover {
        border: 1px solid #3b82f6;
    }
    QComboBox::drop-down {
        border: none;
        width: 30px;
    }
    QComboBox QLineEdit {
        border: none;
        background: transparent;
        padding: 0;
        color: #1f2937;
    }
"""

_LIST_VIEW_STYLE = """
    QListView {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background-color: white;
        outline: none;
        padding: 4px;
    }
"""


def _ensure_font(widget) -> QFont:
    font = QFont(widget.font())
    if font.pointSize() <= 0:
        if font.pixelSize() > 0:
            font.setPointSize(max(1, round(font.pixelSize() * 0.75)))
        else:
            font.setPointSize(10)
        widget.setFont(font)
    return font


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


class CheckableComboBox(QComboBox):
    """Multi-select dropdown with checkable model items; popup stays open on click."""

    selection_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_mode = True
        self._selected_ids: set[int] = set()
        self._updating = False
        self._skip_hide_popup = False

        _ensure_font(self)

        self.setEditable(True)
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setReadOnly(True)
        self.lineEdit.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lineEdit.setCursor(Qt.CursorShape.ArrowCursor)
        _ensure_font(self.lineEdit)
        self.setLineEdit(self.lineEdit)
        self.lineEdit.installEventFilter(self)

        model = QStandardItemModel(self)
        self.setModel(model)

        list_view = QListView(self)
        list_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_view.setMinimumWidth(340)
        list_view.setUniformItemSizes(True)
        _ensure_font(list_view)
        list_view.setItemDelegate(_CheckableListDelegate(list_view))
        self.setView(list_view)
        list_view.viewport().installEventFilter(self)

        self.setStyleSheet(_COMBO_STYLE)
        list_view.setStyleSheet(_LIST_VIEW_STYLE)
        self.setMaxVisibleItems(12)

        self._restore_selection()
        self.reload_decks()

    def showPopup(self) -> None:
        view = self.view()
        if view is not None:
            _ensure_font(view)
        super().showPopup()

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

    def hidePopup(self) -> None:
        if self._skip_hide_popup:
            return
        super().hidePopup()
        self.update_display_text()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.lineEdit:
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
            ):
                if event.type() == QEvent.Type.MouseButtonPress:
                    self.showPopup()
                return True

        view = self.view()
        if view is not None and watched is view.viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                self._skip_hide_popup = True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                pos = (
                    event.position().toPoint()
                    if hasattr(event, "position")
                    else event.pos()
                )
                index = view.indexAt(pos)
                if index.isValid():
                    self._handle_item_click(index)
                self._skip_hide_popup = False
                return True
        return super().eventFilter(watched, event)

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

        self.lineEdit.setText(text)

    def _model(self) -> QStandardItemModel:
        model = self.model()
        assert isinstance(model, QStandardItemModel)
        return model

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
        model = self._model()
        model.clear()

        model.appendRow(self._make_checkable_item(tr("learning.quiz_decks_all"), _ALL_ITEM_ID))

        for deck in decks:
            stats = learning.get_quiz_coverage(deck.id)
            text = tr(
                "learning.quiz_deck_short_item",
                name=deck.name,
                ready=stats.ready,
                eligible=stats.eligible,
            )
            model.appendRow(self._make_checkable_item(text, deck.id))

        self._apply_check_states_to_model()
        self._updating = False

    def _apply_check_states_to_model(self) -> None:
        model = self._model()
        deck_total = model.rowCount() - 1

        for row in range(1, model.rowCount()):
            item = model.item(row)
            if item is None:
                continue
            deck_id = item.data(_DECK_ID_ROLE)
            checked = isinstance(deck_id, int) and deck_id in self._selected_ids
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

        all_item = model.item(0)
        if all_item is None:
            return

        checked_count = sum(
            1
            for row in range(1, model.rowCount())
            if model.item(row) is not None
            and model.item(row).checkState() == Qt.CheckState.Checked
        )
        if deck_total > 0 and checked_count == deck_total:
            all_item.setCheckState(Qt.CheckState.Checked)
        else:
            all_item.setCheckState(Qt.CheckState.Unchecked)

    def _set_all_items_check_state(self, state: Qt.CheckState) -> None:
        model = self._model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is not None:
                item.setCheckState(state)

    def _handle_item_click(self, index: QModelIndex) -> None:
        if self._updating or not index.isValid():
            return
        item = self._model().itemFromIndex(index)
        if item is None:
            return

        self._updating = True
        deck_id = item.data(_DECK_ID_ROLE)
        model = self._model()

        if deck_id == _ALL_ITEM_ID:
            deck_total = model.rowCount() - 1
            all_selected = self._all_mode or (
                deck_total > 0 and len(self._selected_ids) == deck_total
            )
            select_all = not all_selected
            if select_all:
                self._all_mode = True
                self._selected_ids = {
                    model.item(row).data(_DECK_ID_ROLE)
                    for row in range(1, model.rowCount())
                    if model.item(row) is not None
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

            deck_total = model.rowCount() - 1
            self._all_mode = deck_total > 0 and len(self._selected_ids) == deck_total
            self._apply_check_states_to_model()

        self._updating = False
        view = self.view()
        if view is not None:
            view.viewport().update()
        self.update_display_text()
        self._emit_selection()

    def _emit_selection(self) -> None:
        deck_ids = self.selected_deck_ids()
        save_play_deck_ids(deck_ids)
        self.selection_changed.emit(deck_ids)


QuizDeckComboBox = CheckableComboBox
