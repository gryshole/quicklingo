from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QLineEdit, QVBoxLayout

from quicklingo import settings
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab


class ApiKeysTab(SettingsTab):
    api_keys_saved = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._group = QGroupBox()
        self._form = QFormLayout(self._group)

        self._groq_label = QLabel()
        self._groq_field = QLineEdit()
        self._groq_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._groq_field.textChanged.connect(self.mark_dirty)

        self._gemini_label = QLabel()
        self._gemini_field = QLineEdit()
        self._gemini_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_field.textChanged.connect(self.mark_dirty)

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setOpenExternalLinks(True)

        self._form.addRow(self._groq_label, self._groq_field)
        self._form.addRow(self._gemini_label, self._gemini_field)
        self._form.addRow("", self._note)
        layout.addWidget(self._group)
        layout.addStretch()
        self.reload()

    def retranslate_ui(self) -> None:
        self._group.setTitle(tr("settings.api_keys.group"))
        self._groq_label.setText(tr("settings.api_keys.groq"))
        self._gemini_label.setText(tr("settings.api_keys.gemini"))
        self._note.setText(tr("settings.api_keys.note"))

    def reload(self) -> None:
        groq, gemini = settings.get_api_keys()
        self._groq_field.blockSignals(True)
        self._gemini_field.blockSignals(True)
        self._groq_field.setText(groq)
        self._gemini_field.setText(gemini)
        self._groq_field.blockSignals(False)
        self._gemini_field.blockSignals(False)
        self.retranslate_ui()
        self.mark_clean()

    def save(self) -> bool:
        settings.save_api_keys(
            groq=self._groq_field.text(),
            gemini=self._gemini_field.text(),
        )
        self.mark_clean()
        self.api_keys_saved.emit()
        return True
