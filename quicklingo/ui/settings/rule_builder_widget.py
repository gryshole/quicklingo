from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quicklingo.i18n import tr

RULE_TYPE_IDS = [
    "escape_plain",
    "normalize_separators",
    "split_blocks",
    "foreach_block",
    "format_ua_en_block",
    "format_en_ua_blocks",
    "wrap_card",
    "wrap_document",
    "line_style",
]


class RuleBuilderWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 3)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton()
        self._add_btn.clicked.connect(self._add_rule)
        self._up_btn = QPushButton("↑")
        self._up_btn.clicked.connect(lambda: self._move(-1))
        self._down_btn = QPushButton("↓")
        self._down_btn.clicked.connect(lambda: self._move(1))
        self._del_btn = QPushButton()
        self._del_btn.clicked.connect(self._remove_rule)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._up_btn)
        btn_row.addWidget(self._down_btn)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._table.setHorizontalHeaderLabels(
            ["#", tr("settings.rules.col_type"), tr("settings.rules.col_params")]
        )
        self._add_btn.setText(tr("settings.rules.add"))
        self._del_btn.setText(tr("common.delete"))
        for row in range(self._table.rowCount()):
            combo = self._table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                current = combo.currentData()
                combo.blockSignals(True)
                combo.clear()
                for type_id in RULE_TYPE_IDS:
                    combo.addItem(tr(f"settings.rules.type_{type_id}"), type_id)
                idx = combo.findData(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                combo.blockSignals(False)

    def set_rules(self, rules: list[dict[str, Any]]) -> None:
        self._table.setRowCount(0)
        for rule in rules:
            self._append_row(rule)

    def get_rules(self) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for row in range(self._table.rowCount()):
            combo = self._table.cellWidget(row, 1)
            params_item = self._table.item(row, 2)
            if not isinstance(combo, QComboBox):
                continue
            type_id = combo.currentData()
            rule: dict[str, Any] = {"type": type_id}
            if params_item and params_item.text().strip():
                try:
                    extra = json.loads(params_item.text())
                    if isinstance(extra, dict):
                        rule.update(extra)
                except json.JSONDecodeError:
                    pass
            rules.append(rule)
        return rules

    def _append_row(self, rule: dict[str, Any]) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        combo = QComboBox()
        for type_id in RULE_TYPE_IDS:
            combo.addItem(tr(f"settings.rules.type_{type_id}"), type_id)
        rtype = rule.get("type", "escape_plain")
        idx = combo.findData(rtype)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self._table.setCellWidget(row, 1, combo)
        params = {k: v for k, v in rule.items() if k != "type"}
        params_text = json.dumps(params, ensure_ascii=False) if params else ""
        if rtype == "split_blocks" and "pattern" in rule:
            params_text = json.dumps({"pattern": rule["pattern"]}, ensure_ascii=False)
        if rtype == "foreach_block" and "rules" in rule:
            params_text = json.dumps({"rules": rule["rules"]}, ensure_ascii=False)
        self._table.setItem(row, 2, QTableWidgetItem(params_text))

    def _add_rule(self) -> None:
        self._append_row({"type": "escape_plain"})

    def _remove_rule(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item:
                item.setText(str(i + 1))

    def _move(self, delta: int) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self._table.rowCount():
            return
        rules = self.get_rules()
        rules[row], rules[new_row] = rules[new_row], rules[row]
        self.set_rules(rules)
        self._table.setCurrentCell(new_row, 1)
