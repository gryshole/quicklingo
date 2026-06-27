from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from quicklingo import settings
from quicklingo.i18n import tr
from quicklingo.providers.setup_info import KEY_PROVIDERS, PROVIDER_HINT_KEYS
from quicklingo.ui.settings.base_tab import SettingsTab


class ApiKeysTab(SettingsTab):
    api_keys_saved = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        self._group = QGroupBox()
        self._form = QFormLayout(self._group)
        self._fields: dict[str, QLineEdit] = {}
        self._hints: dict[str, QLabel] = {}

        for provider in KEY_PROVIDERS:
            field = QLineEdit()
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.textChanged.connect(self.mark_dirty)
            hint = QLabel()
            hint.setWordWrap(True)
            hint.setOpenExternalLinks(True)
            hint.setTextFormat(Qt.TextFormat.RichText)
            label = QLabel()
            self._fields[provider] = field
            self._hints[provider] = hint
            self._form.addRow(label, field)
            self._form.addRow("", hint)
            setattr(self, f"_{provider}_label", label)

        self._ollama_url_label = QLabel()
        self._ollama_url_field = QLineEdit()
        self._ollama_url_field.textChanged.connect(self.mark_dirty)
        self._ollama_url_hint = QLabel()
        self._ollama_url_hint.setWordWrap(True)
        self._ollama_url_hint.setOpenExternalLinks(True)
        self._ollama_url_hint.setTextFormat(Qt.TextFormat.RichText)

        self._ollama_key_label = QLabel()
        self._ollama_key_field = QLineEdit()
        self._ollama_key_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._ollama_key_field.textChanged.connect(self.mark_dirty)
        self._ollama_key_hint = QLabel()
        self._ollama_key_hint.setWordWrap(True)
        self._ollama_key_hint.setOpenExternalLinks(True)
        self._ollama_key_hint.setTextFormat(Qt.TextFormat.RichText)

        self._form.addRow(self._ollama_url_label, self._ollama_url_field)
        self._form.addRow("", self._ollama_url_hint)
        self._form.addRow(self._ollama_key_label, self._ollama_key_field)
        self._form.addRow("", self._ollama_key_hint)

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._form.addRow("", self._note)

        layout.addWidget(self._group)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.reload()

    def retranslate_ui(self) -> None:
        self._group.setTitle(tr("settings.api_keys.group"))
        for provider in KEY_PROVIDERS:
            getattr(self, f"_{provider}_label").setText(tr(f"settings.api_keys.{provider}"))
            self._fields[provider].setPlaceholderText(tr(f"settings.api_keys.placeholder_{provider}"))
            self._hints[provider].setText(tr(PROVIDER_HINT_KEYS[provider]))
        self._ollama_url_label.setText(tr("settings.api_keys.ollama_url"))
        self._ollama_url_field.setPlaceholderText(tr("settings.api_keys.placeholder_ollama_url"))
        self._ollama_url_hint.setText(tr(PROVIDER_HINT_KEYS["ollama"]))
        self._ollama_key_label.setText(tr("settings.api_keys.ollama_key"))
        self._ollama_key_field.setPlaceholderText(tr("settings.api_keys.placeholder_ollama_key"))
        self._ollama_key_hint.setText(tr("settings.api_keys.hint_ollama_key"))
        self._note.setText(tr("settings.api_keys.note"))

    def reload(self) -> None:
        keys = settings.get_api_keys()
        for provider in KEY_PROVIDERS:
            field = self._fields[provider]
            field.blockSignals(True)
            field.setText(keys.get(provider, ""))
            field.blockSignals(False)
        self._ollama_url_field.blockSignals(True)
        self._ollama_url_field.setText(settings.get_ollama_base_url())
        self._ollama_url_field.blockSignals(False)
        self._ollama_key_field.blockSignals(True)
        self._ollama_key_field.setText(keys.get("ollama", ""))
        self._ollama_key_field.blockSignals(False)
        self.retranslate_ui()
        self.mark_clean()

    def save(self) -> bool:
        settings.save_api_keys(
            groq=self._fields["groq"].text(),
            gemini=self._fields["gemini"].text(),
            openrouter=self._fields["openrouter"].text(),
            mistral=self._fields["mistral"].text(),
            ollama=self._ollama_key_field.text(),
            deepseek=self._fields["deepseek"].text(),
            openai=self._fields["openai"].text(),
            anthropic=self._fields["anthropic"].text(),
        )
        settings.save_ollama_base_url(self._ollama_url_field.text())
        self.mark_clean()
        self.api_keys_saved.emit()
        return True
