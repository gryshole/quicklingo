from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from quicklingo.config.loader import get_direction_label, get_directions
from quicklingo.features import get_feature, is_enabled
from quicklingo.i18n import tr
from quicklingo.learning import word_frequency


class WordFrequencyWindow(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.resize(480, 520)
        layout = QVBoxLayout(self)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._direction_combo_label = QLabel()
        self._direction_buttons: list[tuple[QPushButton, str]] = []
        btn_row = QHBoxLayout()
        for direction in get_directions():
            btn = QPushButton(direction.label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, d=direction.id, b=btn: self._select_direction(d, b))
            self._direction_buttons.append((btn, direction.id))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["", ""])
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._summary)
        layout.addWidget(self._direction_combo_label)
        layout.addLayout(btn_row)
        layout.addWidget(self._table, stretch=1)
        self._current_direction = get_directions()[0].id if get_directions() else "ua-en"
        if self._direction_buttons:
            self._direction_buttons[0][0].setChecked(True)
        self.retranslate_ui()
        self.refresh()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("learning.word_freq_title"))
        self._direction_combo_label.setText(tr("learning.word_freq_direction"))
        self._table.setHorizontalHeaderLabels(
            [tr("learning.word_freq_word"), tr("learning.word_freq_count")]
        )
        self.refresh()

    def _select_direction(self, direction_id: str, active_btn: QPushButton) -> None:
        self._current_direction = direction_id
        for btn, _ in self._direction_buttons:
            if btn is not active_btn:
                btn.setChecked(False)
        active_btn.setChecked(True)
        self.refresh()

    def refresh(self) -> None:
        if not is_enabled("learning.word_frequency"):
            self._summary.setText(tr("learning.word_freq_disabled"))
            self._table.setRowCount(0)
            return
        top_n = int(get_feature("learning.word_frequency").get("top_n", 50))
        words = word_frequency.compute_top_words(self._current_direction, top_n=top_n)
        self._summary.setText(
            tr(
                "learning.word_freq_summary",
                direction=get_direction_label(self._current_direction),
                count=len(words),
            )
        )
        self._table.setRowCount(len(words))
        for row, (word, count) in enumerate(words):
            self._table.setItem(row, 0, QTableWidgetItem(word))
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 1, count_item)
