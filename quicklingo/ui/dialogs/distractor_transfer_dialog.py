from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from quicklingo.db import history, learning
from quicklingo.i18n import tr
from quicklingo.learning.quiz.distractor_deck import filter_user_decks
from quicklingo.ui.qt_utils import configure_single_line_combo


class DistractorTransferDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        direction: str,
        selected_count: int,
    ) -> None:
        super().__init__(parent)
        self._direction = direction
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        self._hint_label = QLabel()
        self._hint_label.setWordWrap(True)
        layout.addWidget(self._hint_label)

        form = QFormLayout()
        self._tag_combo = QComboBox()
        configure_single_line_combo(self._tag_combo)
        self._tag_combo.setEditable(True)
        self._tag_combo.lineEdit().setPlaceholderText(tr("learning.distractor_decks_tag_placeholder"))
        self._deck_name_field = QLineEdit()
        self._deck_name_field.setPlaceholderText(tr("learning.distractor_decks_name_placeholder"))
        form.addRow(tr("learning.distractor_decks_target_tag"), self._tag_combo)
        form.addRow(tr("learning.distractor_decks_target_name"), self._deck_name_field)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._reload_tags()
        self.retranslate_ui(selected_count)

    def retranslate_ui(self, selected_count: int | None = None) -> None:
        self.setWindowTitle(tr("learning.distractor_decks_transfer_title"))
        count = selected_count if selected_count is not None else 0
        self._hint_label.setText(
            tr("learning.distractor_decks_transfer_hint", count=count)
        )

    def _reload_tags(self) -> None:
        current = self._tag_combo.currentText().strip()
        tags: list[str] = []
        seen: set[str] = set()
        for tag, _count in history.get_tag_counts(
            direction=self._direction, learning_kind=True
        ):
            if tag and tag not in seen:
                seen.add(tag)
                tags.append(tag)
        for deck in filter_user_decks(learning.list_decks()):
            if deck.direction != self._direction:
                continue
            tag = (deck.tag or "").strip()
            if tag and tag not in seen:
                seen.add(tag)
                tags.append(tag)
        tags.sort(key=str.lower)
        self._tag_combo.blockSignals(True)
        self._tag_combo.clear()
        for tag in tags:
            self._tag_combo.addItem(tag, tag)
        if current:
            index = self._tag_combo.findText(current)
            if index >= 0:
                self._tag_combo.setCurrentIndex(index)
            else:
                self._tag_combo.setEditText(current)
        self._tag_combo.blockSignals(False)

    def target_tag(self) -> str:
        return self._tag_combo.currentText().strip()

    def deck_name(self) -> str:
        name = self._deck_name_field.text().strip()
        return name or self.target_tag()
