from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from quicklingo.db import history

_DIRECTION_LABELS = {
    "ua-en": "Укр → Англ",
    "en-ua": "Англ → Укр",
}


class HistoryWindow(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Історія запитів")
        self.resize(720, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)

        refresh_btn = QPushButton("Оновити")
        refresh_btn.clicked.connect(self.refresh)

        clear_btn = QPushButton("Очистити")
        clear_btn.clicked.connect(self._clear_history)

        top_row = QHBoxLayout()
        top_row.addWidget(self._summary_label, stretch=1)
        top_row.addWidget(refresh_btn)
        top_row.addWidget(clear_btn)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Дата", "Напрямок", "Запит", "Модель", "Результат", ""]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setMinimumSectionSize(48)
        header.setStretchLastSection(False)
        for col in range(5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 150)
        header.resizeSection(1, 100)
        header.resizeSection(2, 120)
        header.resizeSection(3, 160)
        header.resizeSection(4, 220)
        header.resizeSection(5, 36)

        self._table.itemSelectionChanged.connect(self._on_row_selected)

        detail_label = QLabel("Повний результат:")
        self._detail_field = QTextEdit()
        self._detail_field.setReadOnly(True)
        self._detail_field.setPlaceholderText("Оберіть рядок у таблиці…")

        layout.addLayout(top_row)
        layout.addWidget(self._table, stretch=2)
        layout.addWidget(detail_label)
        layout.addWidget(self._detail_field, stretch=1)

        self._records: list[history.TranslationRecord] = []
        self.refresh()

    def refresh(self) -> None:
        stats = history.get_stats()
        self._records = history.get_all()
        shown = len(self._records)

        self._summary_label.setText(
            f"Усього записів: {stats['total']}  ·  "
            f"Укр→Англ: {stats['ua_en']}  ·  "
            f"Англ→Укр: {stats['en_ua']}"
            + (f"  ·  показано останні {shown}" if shown < stats["total"] else "")
        )

        self._detail_field.clear()

        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for row_idx, record in enumerate(self._records):
                self._table.insertRow(row_idx)
                values = [
                    record.created_at,
                    _DIRECTION_LABELS.get(record.direction, record.direction),
                    record.source_text,
                    record.model,
                    _preview(record.result_text),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value if col != 4 else record.result_text)
                    if col in (0, 1, 3):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignTop)
                    self._table.setItem(row_idx, col, item)

                delete_btn = QPushButton("✕")
                delete_btn.setToolTip("Видалити")
                delete_btn.setFixedWidth(32)
                delete_btn.clicked.connect(
                    lambda _checked=False, rid=record.id: self._delete_record(rid)
                )
                self._table.setCellWidget(row_idx, 5, delete_btn)

            if self._records:
                self._table.selectRow(0)
        finally:
            self._table.blockSignals(False)

        self._on_row_selected()

    def _delete_record(self, record_id: int) -> None:
        if not history.delete_by_id(record_id):
            return
        self.refresh()

    def _clear_history(self) -> None:
        stats = history.get_stats()
        if stats["total"] == 0:
            return

        answer = QMessageBox.question(
            self,
            "Очистити історію",
            "Ви точно хочете очистити всю історію запитів?\n"
            "Цю дію не можна скасувати.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        history.clear_all()
        self.refresh()

    def _on_row_selected(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._detail_field.clear()
            return
        row = rows[0].row()
        if row < 0 or row >= len(self._records):
            self._detail_field.clear()
            return
        self._detail_field.setPlainText(self._records[row].result_text)


def _preview(text: str, max_len: int = 120) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"
