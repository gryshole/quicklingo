from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from quicklingo.i18n import tr


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
        answer = QMessageBox.question(
            self,
            tr("common.unsaved_title"),
            tr("common.unsaved_message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    @staticmethod
    def show_error(parent: QWidget, message: str) -> None:
        QMessageBox.warning(parent, tr("common.error"), message)

    def confirm_delete(self, message: str) -> bool:
        answer = QMessageBox.question(
            self,
            tr("common.confirm"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
