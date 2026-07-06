from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from quicklingo import settings
from quicklingo.i18n import tr
from quicklingo.providers.setup_info import KEY_PROVIDERS, PROVIDER_HINT_KEYS
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings_theme import (
    align_form_labels,
    configure_api_key_hint,
    configure_api_key_label,
    configure_password_field,
    configure_settings_card,
    style_api_key_hint_text,
)


class ApiKeysTab(SettingsTab):
    api_keys_saved = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("settingsTabBody")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        card = QWidget()
        configure_settings_card(card)
        self._form = QFormLayout(card)
        self._form.setContentsMargins(15, 15, 15, 15)
        self._form.setVerticalSpacing(10)
        self._form.setHorizontalSpacing(10)
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._fields: dict[str, QLineEdit] = {}
        self._hints: dict[str, QLabel] = {}
        self._labels: list[QLabel] = []

        for index, provider in enumerate(KEY_PROVIDERS):
            field = QLineEdit()
            configure_password_field(field)
            field.textChanged.connect(self.mark_dirty)
            hint = QLabel()
            configure_api_key_hint(hint)
            label = QLabel()
            configure_api_key_label(label, spaced=index > 0)
            self._fields[provider] = field
            self._hints[provider] = hint
            self._labels.append(label)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._form.addRow(label, field)
            self._form.addRow(hint)
            setattr(self, f"_{provider}_label", label)

        self._ollama_url_label = QLabel()
        configure_api_key_label(self._ollama_url_label)
        self._ollama_url_field = QLineEdit()
        self._ollama_url_field.textChanged.connect(self.mark_dirty)
        self._ollama_url_hint = QLabel()
        configure_api_key_hint(self._ollama_url_hint)
        self._ollama_key_label = QLabel()
        configure_api_key_label(self._ollama_key_label)
        self._ollama_key_field = QLineEdit()
        configure_password_field(self._ollama_key_field)
        self._ollama_key_field.textChanged.connect(self.mark_dirty)
        self._ollama_key_hint = QLabel()
        configure_api_key_hint(self._ollama_key_hint)
        self._labels.extend(
            (self._ollama_url_label, self._ollama_key_label)
        )

        self._ollama_url_field.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._ollama_key_field.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._form.addRow(self._ollama_url_label, self._ollama_url_field)
        self._form.addRow(self._ollama_url_hint)
        self._form.addRow(self._ollama_key_label, self._ollama_key_field)
        self._form.addRow(self._ollama_key_hint)

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setObjectName("apiKeyNote")
        self._form.addRow(self._note)

        bottom_spacer = QWidget()
        bottom_spacer.setFixedHeight(20)
        self._form.addRow(bottom_spacer)

        content_layout.addWidget(card)
        content_layout.addSpacing(25)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.reload()

    def retranslate_ui(self) -> None:
        for provider in KEY_PROVIDERS:
            getattr(self, f"_{provider}_label").setText(tr(f"settings.api_keys.{provider}"))
            self._fields[provider].setPlaceholderText(
                tr(f"settings.api_keys.placeholder_{provider}")
            )
            self._hints[provider].setText(
                style_api_key_hint_text(tr(PROVIDER_HINT_KEYS[provider]))
            )
        self._ollama_url_label.setText(tr("settings.api_keys.ollama_url"))
        self._ollama_url_field.setPlaceholderText(tr("settings.api_keys.placeholder_ollama_url"))
        self._ollama_url_hint.setText(
            style_api_key_hint_text(tr(PROVIDER_HINT_KEYS["ollama"]))
        )
        self._ollama_key_label.setText(tr("settings.api_keys.ollama_key"))
        self._ollama_key_field.setPlaceholderText(tr("settings.api_keys.placeholder_ollama_key"))
        self._ollama_key_hint.setText(
            style_api_key_hint_text(tr("settings.api_keys.hint_ollama_key"))
        )
        self._note.setText(tr("settings.api_keys.note"))
        align_form_labels(self._labels)

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
