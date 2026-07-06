from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from quicklingo import settings
from quicklingo.i18n import tr
from quicklingo.providers.ollama_models import fetch_ollama_model_ids
from quicklingo.providers.registry import (
    DEFAULT_MAIN_MODEL_IDS,
    get_model_catalog,
    get_model_entry,
    parse_model_id,
)
from quicklingo.providers.setup_info import API_PROVIDERS
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings_theme import configure_models_tab_widgets, configure_settings_group_box

_PROVIDER_ROLE = Qt.ItemDataRole.UserRole + 1


class ModelsTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        self._intro = QLabel()
        self._intro.setWordWrap(True)
        layout.addWidget(self._intro)

        self._group = QGroupBox()
        group_layout = QVBoxLayout(self._group)
        group_layout.setSpacing(10)
        self._selected_label = QLabel()
        group_layout.addWidget(self._selected_label)

        self._selected = QListWidget()
        self._selected.currentRowChanged.connect(self._update_buttons)
        group_layout.addWidget(self._selected)

        add_row = QHBoxLayout()
        self._provider_filter = QComboBox()
        for provider in API_PROVIDERS:
            self._provider_filter.addItem("", provider)
        self._provider_filter.currentIndexChanged.connect(self._on_provider_filter_changed)
        self._add_combo = QComboBox()
        self._add_combo.setEditable(True)
        self._add_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._add_combo.lineEdit().textChanged.connect(self._update_add_button)
        self._add_btn = QPushButton()
        self._add_btn.clicked.connect(self._add_model)
        add_row.addWidget(self._provider_filter)
        add_row.addWidget(self._add_combo, stretch=1)
        add_row.addWidget(self._add_btn)
        group_layout.addLayout(add_row)

        btn_row = QHBoxLayout()
        self._remove_btn = QPushButton()
        self._remove_btn.clicked.connect(self._remove_selected)
        self._up_btn = QPushButton()
        self._up_btn.clicked.connect(self._move_up)
        self._down_btn = QPushButton()
        self._down_btn.clicked.connect(self._move_down)
        self._reset_btn = QPushButton()
        self._reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(self._remove_btn)
        btn_row.addWidget(self._up_btn)
        btn_row.addWidget(self._down_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._reset_btn)
        group_layout.addLayout(btn_row)

        configure_settings_group_box(self._group)
        configure_models_tab_widgets(
            list_widget=self._selected,
            add_btn=self._add_btn,
            remove_btn=self._remove_btn,
            up_btn=self._up_btn,
            down_btn=self._down_btn,
            reset_btn=self._reset_btn,
        )
        layout.addWidget(self._group)
        layout.addStretch()
        self.retranslate_ui()
        self.reload()

    def retranslate_ui(self) -> None:
        self._intro.setText(tr("settings.models.intro"))
        self._group.setTitle(tr("settings.models.group"))
        self._selected_label.setText(tr("settings.models.selected"))
        self._add_combo.lineEdit().setPlaceholderText(tr("settings.models.add_placeholder"))
        self._add_btn.setText(tr("settings.models.add"))
        self._remove_btn.setText(tr("settings.models.remove"))
        self._up_btn.setText(tr("settings.models.move_up"))
        self._down_btn.setText(tr("settings.models.move_down"))
        self._reset_btn.setText(tr("settings.models.reset_defaults"))
        for index, provider in enumerate(API_PROVIDERS):
            self._provider_filter.setItemText(index, tr(f"settings.api_keys.provider_{provider}"))
        self._refresh_add_combo()

    def reload(self) -> None:
        self._set_provider_filter(settings.get_models_add_provider())
        self._populate_selected(
            settings.get_main_model_ids(),
            settings.get_custom_model_providers(),
        )
        self._refresh_add_combo()
        self._update_buttons()
        self.mark_clean()

    def _set_provider_filter(self, provider: str) -> None:
        index = self._provider_filter.findData(provider)
        if index < 0:
            index = 0
        self._provider_filter.blockSignals(True)
        self._provider_filter.setCurrentIndex(index)
        self._provider_filter.blockSignals(False)

    def _filter_provider(self) -> str:
        provider = self._provider_filter.currentData()
        return provider if provider in API_PROVIDERS else "groq"

    def _display_name_for(self, model_id: str, provider: str | None = None) -> str:
        entry = get_model_entry(model_id)
        if entry is not None:
            return entry.display_name
        api_provider = provider or self._filter_provider()
        provider_label = tr(f"settings.api_keys.provider_{api_provider}")
        return f"{model_id} ({provider_label})"

    def _populate_selected(
        self,
        model_ids: list[str],
        custom_providers: dict[str, str],
    ) -> None:
        self._selected.blockSignals(True)
        self._selected.clear()
        for model_id in model_ids:
            cleaned, parsed_provider = parse_model_id(model_id)
            if not cleaned:
                continue
            provider = custom_providers.get(cleaned, parsed_provider)
            item = QListWidgetItem(self._display_name_for(cleaned, provider))
            item.setData(Qt.ItemDataRole.UserRole, cleaned)
            if get_model_entry(cleaned) is None:
                item.setData(_PROVIDER_ROLE, provider)
            self._selected.addItem(item)
        self._selected.blockSignals(False)

    def _selected_ids(self) -> list[str]:
        ids: list[str] = []
        for row in range(self._selected.count()):
            item = self._selected.item(row)
            model_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(model_id, str):
                ids.append(model_id)
        return ids

    def _custom_providers_from_list(self) -> dict[str, str]:
        providers: dict[str, str] = {}
        for row in range(self._selected.count()):
            item = self._selected.item(row)
            model_id = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(model_id, str) or get_model_entry(model_id) is not None:
                continue
            provider = item.data(_PROVIDER_ROLE)
            if isinstance(provider, str) and provider in API_PROVIDERS:
                providers[model_id] = provider
        return providers

    def _on_provider_filter_changed(self, _index: int) -> None:
        self._refresh_add_combo()
        self.mark_dirty()

    def _refresh_add_combo(self) -> None:
        selected = set(self._selected_ids())
        typed = self._add_combo.currentText()
        filter_provider = self._filter_provider()
        self._add_combo.blockSignals(True)
        self._add_combo.clear()
        catalog = get_model_catalog()
        catalog_ids = {entry.model_id for entry in catalog}
        for entry in catalog:
            if entry.api_provider != filter_provider:
                continue
            if entry.model_id in selected:
                continue
            self._add_combo.addItem(entry.display_name, entry.model_id)
        if filter_provider == "ollama":
            for model_id in fetch_ollama_model_ids():
                if model_id in selected or model_id in catalog_ids:
                    continue
                self._add_combo.addItem(model_id, model_id)
        self._add_combo.setEditText(typed)
        self._add_combo.blockSignals(False)
        self._update_add_button()

    def _resolve_add_input(self) -> tuple[str | None, str | None]:
        text = self._add_combo.currentText().strip()
        if not text:
            return None, None
        index = self._add_combo.currentIndex()
        if index >= 0 and self._add_combo.itemText(index) == text:
            data = self._add_combo.itemData(index)
            if isinstance(data, str):
                entry = get_model_entry(data.strip())
                if entry is not None:
                    return entry.model_id, entry.api_provider
        cleaned, prefix_provider = parse_model_id(text)
        if not cleaned:
            return None, None
        lowered = text.lower()
        if lowered.startswith(tuple(f"{provider}:" for provider in API_PROVIDERS)):
            return cleaned, prefix_provider
        return cleaned, self._filter_provider()

    def _update_add_button(self) -> None:
        model_id, _provider = self._resolve_add_input()
        if not model_id:
            self._add_btn.setEnabled(False)
            return
        self._add_btn.setEnabled(model_id not in self._selected_ids())

    def _update_buttons(self) -> None:
        row = self._selected.currentRow()
        count = self._selected.count()
        self._remove_btn.setEnabled(row >= 0 and count > 1)
        self._up_btn.setEnabled(row > 0)
        self._down_btn.setEnabled(row >= 0 and row < count - 1)
        self._update_add_button()

    def _add_model(self) -> None:
        model_id, provider = self._resolve_add_input()
        if not model_id or provider is None:
            self.show_error(self, tr("settings.models.error_empty"))
            return
        if model_id in self._selected_ids():
            self.show_error(self, tr("settings.models.error_duplicate"))
            return
        entry = get_model_entry(model_id)
        item = QListWidgetItem(self._display_name_for(model_id, provider))
        item.setData(Qt.ItemDataRole.UserRole, model_id)
        if entry is None:
            item.setData(_PROVIDER_ROLE, provider)
        self._selected.addItem(item)
        self._selected.setCurrentItem(item)
        self._add_combo.setEditText("")
        self._refresh_add_combo()
        self._update_buttons()
        self.mark_dirty()

    def _remove_selected(self) -> None:
        row = self._selected.currentRow()
        if row < 0 or self._selected.count() <= 1:
            return
        self._selected.takeItem(row)
        if row >= self._selected.count():
            row = self._selected.count() - 1
        if row >= 0:
            self._selected.setCurrentRow(row)
        self._refresh_add_combo()
        self._update_buttons()
        self.mark_dirty()

    def _move_up(self) -> None:
        row = self._selected.currentRow()
        if row <= 0:
            return
        item = self._selected.takeItem(row)
        self._selected.insertItem(row - 1, item)
        self._selected.setCurrentRow(row - 1)
        self._update_buttons()
        self.mark_dirty()

    def _move_down(self) -> None:
        row = self._selected.currentRow()
        if row < 0 or row >= self._selected.count() - 1:
            return
        item = self._selected.takeItem(row)
        self._selected.insertItem(row + 1, item)
        self._selected.setCurrentRow(row + 1)
        self._update_buttons()
        self.mark_dirty()

    def _reset_defaults(self) -> None:
        self._populate_selected(list(DEFAULT_MAIN_MODEL_IDS), {})
        self._refresh_add_combo()
        self._update_buttons()
        self.mark_dirty()

    def save(self) -> bool:
        ids = self._selected_ids()
        if not ids:
            self.show_error(self, tr("settings.models.error_empty"))
            return False
        settings.save_main_model_ids(
            ids,
            custom_providers=self._custom_providers_from_list(),
        )
        settings.save_models_add_provider(self._filter_provider())
        self.mark_clean()
        self.config_saved.emit()
        return True
