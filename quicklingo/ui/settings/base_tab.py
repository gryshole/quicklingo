from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from quicklingo.i18n import tr
from quicklingo.ui.qt_utils import confirm, warn


class SettingsTab(QWidget):
    dirty_changed = Signal(bool)
    config_saved = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._dirty = False

    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False
        self.dirty_changed.emit(False)

    def mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def reload(self) -> None:
        raise NotImplementedError

    def save(self) -> bool:
        raise NotImplementedError

    def retranslate_ui(self) -> None:
        pass

    def confirm_discard(self) -> bool:
        if not self.is_dirty():
            return True
        return confirm(
            self,
            tr("common.unsaved_message"),
            title=tr("common.unsaved_title"),
        )

    @staticmethod
    def show_error(parent: QWidget, message: str) -> None:
        warn(parent, message)

    def confirm_delete(self, message: str) -> bool:
        return confirm(self, message)
