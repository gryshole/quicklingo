from __future__ import annotations

import base64
from binascii import Error as BinasciiError

from PySide6.QtCore import QByteArray, QTimer
from PySide6.QtWidgets import QHeaderView, QTableWidget, QWidget

from quicklingo import settings
def remember_geometry_enabled() -> bool:
    return True


def restore_window_geometry(
    widget: QWidget,
    window_id: str,
    *,
    default_width: int,
    default_height: int,
) -> None:
    if not remember_geometry_enabled():
        widget.resize(default_width, default_height)
        return

    encoded = settings.get_tool_window_state(window_id).get("geometry")
    if isinstance(encoded, str) and encoded:
        try:
            raw = base64.b64decode(encoded)
            if widget.restoreGeometry(QByteArray(raw)):
                return
        except (BinasciiError, ValueError):
            pass

    widget.resize(default_width, default_height)


def save_window_geometry(widget: QWidget, window_id: str) -> None:
    if not remember_geometry_enabled():
        return

    encoded = base64.b64encode(bytes(widget.saveGeometry())).decode("ascii")
    settings.save_tool_window_state(window_id, {"geometry": encoded})


def _apply_column_widths(table: QTableWidget, widths: list[int]) -> None:
    header = table.horizontalHeader()
    stretch_last = header.stretchLastSection()
    column_count = table.columnCount()

    for col in range(min(len(widths), column_count)):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

    for col, width in enumerate(widths):
        if col < column_count:
            header.resizeSection(col, max(header.minimumSectionSize(), int(width)))

    if stretch_last and column_count:
        header.setSectionResizeMode(column_count - 1, QHeaderView.ResizeMode.Stretch)


def restore_table_columns(
    table: QTableWidget,
    window_id: str,
    table_id: str,
    *,
    default_widths: list[int],
) -> None:
    if not remember_geometry_enabled():
        _apply_column_widths(table, default_widths)
        return

    columns = settings.get_tool_window_state(window_id).get("columns")
    if not isinstance(columns, dict):
        _apply_column_widths(table, default_widths)
        return

    widths = columns.get(table_id)
    if not isinstance(widths, list) or len(widths) != table.columnCount():
        _apply_column_widths(table, default_widths)
        return

    try:
        parsed = [int(width) for width in widths]
    except (TypeError, ValueError):
        _apply_column_widths(table, default_widths)
        return

    _apply_column_widths(table, parsed)


def save_table_columns(table: QTableWidget, window_id: str, table_id: str) -> None:
    if not remember_geometry_enabled():
        return

    header = table.horizontalHeader()
    widths = [header.sectionSize(col) for col in range(table.columnCount())]
    columns = settings.get_tool_window_state(window_id).get("columns")
    if not isinstance(columns, dict):
        columns = {}
    columns = dict(columns)
    columns[table_id] = widths
    settings.save_tool_window_state(window_id, {"columns": columns})


def bind_table_columns_persistence(
    table: QTableWidget,
    window_id: str,
    table_id: str,
) -> None:
    if not remember_geometry_enabled():
        return

    timer = QTimer(table)
    timer.setSingleShot(True)
    timer.setInterval(300)
    timer.timeout.connect(lambda: save_table_columns(table, window_id, table_id))
    table.horizontalHeader().sectionResized.connect(lambda *_args: timer.start())
    table._column_persist_timer = timer  # keep reference
