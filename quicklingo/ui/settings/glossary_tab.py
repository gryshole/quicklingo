from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from quicklingo.config.loader import get_directions
from quicklingo.i18n import tr
from quicklingo.translation import glossary
from quicklingo.ui.settings.base_tab import SettingsTab


class GlossaryTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._group = QGroupBox()
        form = QFormLayout(self._group)
        self._direction_combo = QComboBox()
        for direction in get_directions():
            self._direction_combo.addItem(direction.label, direction.id)
        self._direction_combo.currentIndexChanged.connect(self._load_direction)
        self._source_field = QLineEdit()
        self._target_field = QLineEdit()
        self._add_btn = QPushButton()
        self._add_btn.clicked.connect(self._add_term)
        self._remove_btn = QPushButton()
        self._remove_btn.clicked.connect(self._remove_selected)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["", ""])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        form.addRow(tr("settings.glossary.direction"), self._direction_combo)
        form.addRow(tr("settings.glossary.source"), self._source_field)
        form.addRow(tr("settings.glossary.target"), self._target_field)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._remove_btn)
        form.addRow(btn_row)
        layout.addWidget(self._group)
        layout.addWidget(self._table, stretch=1)
        self._data: dict[str, list[dict[str, str]]] = {}
        self.reload()

    def retranslate_ui(self) -> None:
        self._group.setTitle(tr("settings.glossary.group"))
        self._add_btn.setText(tr("settings.glossary.add"))
        self._remove_btn.setText(tr("settings.glossary.remove"))
        self._table.setHorizontalHeaderLabels(
            [tr("settings.glossary.source"), tr("settings.glossary.target")]
        )

    def reload(self) -> None:
        self._data = glossary.get_all()
        self._load_direction()
        self.retranslate_ui()
        self.mark_clean()

    def _current_direction(self) -> str:
        return self._direction_combo.currentData() or "ua-en"

    def _load_direction(self) -> None:
        direction = self._current_direction()
        entries = self._data.get(direction, [])
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._table.setItem(row, 0, QTableWidgetItem(entry.get("source", "")))
            self._table.setItem(row, 1, QTableWidgetItem(entry.get("target", "")))

    def _add_term(self) -> None:
        source = self._source_field.text().strip()
        target = self._target_field.text().strip()
        if not source or not target:
            return
        direction = self._current_direction()
        entries = list(self._data.get(direction, []))
        entries.append({"source": source, "target": target})
        self._data[direction] = entries
        self._source_field.clear()
        self._target_field.clear()
        self._load_direction()
        self.mark_dirty()

    def _remove_selected(self) -> None:
        rows = sorted(
            {index.row() for index in self._table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not rows:
            return
        direction = self._current_direction()
        entries = list(self._data.get(direction, []))
        for row in rows:
            if 0 <= row < len(entries):
                entries.pop(row)
        self._data[direction] = entries
        self._load_direction()
        self.mark_dirty()

    def save(self) -> bool:
        glossary.save_all(self._data)
        self.mark_clean()
        return True
