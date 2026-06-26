from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout

from quicklingo import settings
from quicklingo.i18n import get_language, set_language, tr
from quicklingo.ui.settings.base_tab import SettingsTab


class InterfaceTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._group = QGroupBox()
        self._form = QFormLayout(self._group)

        self._language_label = QLabel()
        self._language_combo = QComboBox()
        self._language_combo.addItem("", "en")
        self._language_combo.addItem("", "uk")
        index = self._language_combo.findData(get_language())
        if index >= 0:
            self._language_combo.setCurrentIndex(index)
        self._language_combo.currentIndexChanged.connect(self.mark_dirty)

        self._note = QLabel()
        self._note.setWordWrap(True)

        self._form.addRow(self._language_label, self._language_combo)
        self._form.addRow("", self._note)
        layout.addWidget(self._group)
        layout.addStretch()
        self.retranslate_ui()
        self.mark_clean()

    def retranslate_ui(self) -> None:
        self._group.setTitle(tr("settings.interface.group"))
        self._language_label.setText(tr("settings.interface.language"))
        self._language_combo.setItemText(0, tr("settings.interface.lang_en"))
        self._language_combo.setItemText(1, tr("settings.interface.lang_uk"))
        self._note.setText(tr("settings.interface.note"))

    def reload(self) -> None:
        self._language_combo.blockSignals(True)
        index = self._language_combo.findData(settings.get_ui_language())
        if index >= 0:
            self._language_combo.setCurrentIndex(index)
        self._language_combo.blockSignals(False)
        self.retranslate_ui()
        self.mark_clean()

    def save(self) -> bool:
        lang = self._language_combo.currentData()
        settings.save_ui_language(lang)
        set_language(lang)
        self.mark_clean()
        return True
