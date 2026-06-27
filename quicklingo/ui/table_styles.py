from __future__ import annotations

from PySide6.QtWidgets import QTableWidget

_DATA_TABLE_STYLE = """
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f7f8fa;
    gridline-color: #ebeef2;
    border: 1px solid #d8dde4;
    border-radius: 4px;
    outline: none;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
}
QTableWidget::item {
    padding: 5px 8px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #dbeafe;
    color: #0f172a;
}
QTableWidget::item:selected:active {
    background-color: #bfdbfe;
}
QTableWidget::item:focus {
    border: none;
    outline: none;
    background-color: #dbeafe;
}
QTableWidget:focus {
    outline: none;
}
QHeaderView::section {
    background-color: #f3f4f6;
    color: #374151;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #d8dde4;
    border-right: 1px solid #ebeef2;
    font-weight: 600;
}
QHeaderView::section:last {
    border-right: none;
}
QTableCornerButton::section {
    background-color: #f3f4f6;
    border: none;
    border-bottom: 1px solid #d8dde4;
}
"""

_CELL_ACTION_STYLE = """
QPushButton {
    border: none;
    background: transparent;
    padding: 2px 4px;
    border-radius: 3px;
}
QPushButton:hover {
    background: #bfdbfe;
}
"""


def apply_data_table_style(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.setStyleSheet(_DATA_TABLE_STYLE)


def style_cell_action_button(button) -> None:
    button.setFlat(True)
    button.setStyleSheet(_CELL_ACTION_STYLE)
