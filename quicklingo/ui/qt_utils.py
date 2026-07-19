from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QMessageBox, QSizePolicy, QWidget

from quicklingo.i18n import tr
from quicklingo.ui.app_theme import apply_combo_font
from quicklingo.ui.help_dialog import show_help


def raise_window(widget: QWidget) -> None:
    widget.show()
    widget.raise_()
    widget.activateWindow()


def confirm(parent: QWidget, message: str, *, title: str | None = None) -> bool:
    """Show a Yes/No question dialog; return True only when the user confirms."""
    answer = QMessageBox.question(
        parent,
        title or tr("common.confirm"),
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def warn(parent: QWidget, message: str, *, title: str | None = None) -> None:
    """Show a warning dialog with a default 'error' title."""
    QMessageBox.warning(parent, title or tr("common.error"), message)


def _find_main_window(anchor: QWidget | None):
    from quicklingo.ui.main_window import MainWindow

    widget = anchor
    while widget is not None:
        if isinstance(widget, MainWindow):
            return widget
        widget = widget.parentWidget()
    return None


@contextmanager
def suspend_always_on_top_for_oauth(anchor: QWidget | None = None) -> Iterator[None]:
    """Let the browser take focus during OAuth without breaking modal dialogs."""
    main_window = _find_main_window(anchor)
    host_dialog = anchor.window() if anchor is not None else None

    saved_modality = None

    if main_window is not None:
        if bool(main_window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint):
            main_window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            main_window.show()

    if host_dialog is not None and host_dialog is not main_window:
        saved_modality = host_dialog.windowModality()
        host_dialog.setWindowModality(Qt.WindowModality.NonModal)
        host_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        host_dialog.show()
        host_dialog.lower()
        if main_window is not None:
            main_window.lower()

    try:
        yield
    finally:
        if host_dialog is not None and host_dialog is not main_window:
            if saved_modality is not None and saved_modality != Qt.WindowModality.NonModal:
                host_dialog.setWindowModality(saved_modality)
            host_dialog.setEnabled(True)
            host_dialog.show()
            host_dialog.raise_()
            host_dialog.activateWindow()

        if main_window is not None:
            from quicklingo.features import is_enabled

            want_on_top = is_enabled("ui.always_on_top")
            has_on_top = bool(main_window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
            if want_on_top != has_on_top:
                main_window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, want_on_top)
                main_window.show()


def configure_single_line_combo(combo: QComboBox) -> None:
    """Select-only combo: one-line label, elided popup items, full text in tooltip."""
    combo.setEditable(False)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.view().setTextElideMode(Qt.TextElideMode.ElideRight)
    apply_combo_font(combo)

    def _sync_tooltip(_text: str = "") -> None:
        combo.setToolTip(combo.currentText())

    combo.currentIndexChanged.connect(lambda _index: _sync_tooltip())
    combo.currentTextChanged.connect(_sync_tooltip)
    _sync_tooltip()


def reload_combo(
    combo: QComboBox,
    items: Iterable[tuple[Any, str]],
    *,
    current_data: Any = None,
) -> None:
    if current_data is None and combo.count():
        current_data = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for data, label in items:
        combo.addItem(label, data)
    if current_data is not None:
        index = combo.findData(current_data)
        if index >= 0:
            combo.setCurrentIndex(index)
    combo.blockSignals(False)


def open_help(topic: str, parent: QWidget | None = None) -> None:
    show_help(topic, parent)
