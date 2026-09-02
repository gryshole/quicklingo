from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from quicklingo.config.loader import get_direction_label
from quicklingo.db.learning_models import LearningDeck
from quicklingo.i18n import tr
from quicklingo.providers.registry import get_model_entries
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo


class DeckSplitStartDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        deck: LearningDeck,
        card_count: int,
    ) -> None:
        super().__init__(parent)
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        form = QFormLayout()
        self._note_field = QPlainTextEdit()
        self._note_field.setMaximumHeight(72)
        self._note_field.setPlaceholderText(tr("learning.deck_split_note_placeholder"))
        form.addRow(tr("learning.deck_split_note_label"), self._note_field)

        self._model_combo = QComboBox()
        configure_single_line_combo(self._model_combo)
        reload_combo(
            self._model_combo,
            [(entry.model_id, entry.display_name) for entry in get_model_entries()],
        )
        if self._model_combo.count() and self._model_combo.currentIndex() < 0:
            self._model_combo.setCurrentIndex(0)
        form.addRow(tr("learning.model"), self._model_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setWindowTitle(tr("learning.deck_split_title"))
        self._info_label.setText(
            tr(
                "learning.deck_split_start_info",
                name=deck.name,
                tag=deck.tag,
                direction=get_direction_label(deck.direction),
                count=card_count,
            )
        )

    def user_note(self) -> str:
        return self._note_field.toPlainText().strip()

    def model_index(self) -> int:
        return self._model_combo.currentIndex()
