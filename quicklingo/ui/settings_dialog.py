from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from quicklingo.config.loader import reload_config
from quicklingo.i18n import language_changed, tr
from quicklingo.ui.settings.api_keys_tab import ApiKeysTab
from quicklingo.ui.settings.directions_tab import DirectionsTab
from quicklingo.ui.settings.features_tab import FeaturesTab
from quicklingo.ui.settings.formatters_tab import FormattersTab
from quicklingo.ui.settings.glossary_tab import GlossaryTab
from quicklingo.ui.settings.interface_tab import InterfaceTab
from quicklingo.ui.settings.models_tab import ModelsTab
from quicklingo.ui.settings.profiles_tab import ProfilesTab
from quicklingo.ui.settings.usage_tab import UsageTab


class SettingsDialog(QDialog):
    config_changed = Signal()
    api_keys_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.resize(860, 680)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()

        self._interface_tab = InterfaceTab()
        self._api_keys_tab = ApiKeysTab()
        self._models_tab = ModelsTab()
        self._features_tab = FeaturesTab()
        self._glossary_tab = GlossaryTab()
        self._usage_tab = UsageTab()
        self._directions_tab = DirectionsTab()
        self._profiles_tab = ProfilesTab()
        self._formatters_tab = FormattersTab()

        self._tab_widgets = (
            self._interface_tab,
            self._api_keys_tab,
            self._models_tab,
            self._features_tab,
            self._glossary_tab,
            self._usage_tab,
            self._directions_tab,
            self._profiles_tab,
            self._formatters_tab,
        )

        layout.addWidget(self._tabs)

        for tab in self._tab_widgets:
            if tab not in (self._interface_tab, self._features_tab):
                tab.config_saved.connect(self._on_config_saved)
        self._api_keys_tab.api_keys_saved.connect(self.api_keys_changed.emit)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton()
        self._apply_btn.clicked.connect(self._apply)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._accept)
        self._buttons.rejected.connect(self._reject)
        btn_row.addWidget(self._apply_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._buttons)
        layout.addLayout(btn_row)

        self._config_dirty = False
        self.retranslate_ui()
        language_changed().connect(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("settings.title"))
        self._tabs.clear()
        self._tabs.addTab(self._interface_tab, tr("settings.tab_interface"))
        self._tabs.addTab(self._api_keys_tab, tr("settings.tab_api_keys"))
        self._tabs.addTab(self._models_tab, tr("settings.tab_models"))
        self._tabs.addTab(self._features_tab, tr("settings.tab_features"))
        self._tabs.addTab(self._glossary_tab, tr("settings.tab_glossary"))
        self._tabs.addTab(self._usage_tab, tr("settings.tab_usage"))
        self._tabs.addTab(self._directions_tab, tr("settings.tab_directions"))
        self._tabs.addTab(self._profiles_tab, tr("settings.tab_profiles"))
        self._tabs.addTab(self._formatters_tab, tr("settings.tab_formatters"))
        self._apply_btn.setText(tr("settings.apply"))
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("common.ok"))
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("common.cancel")
        )
        for tab in self._tab_widgets:
            tab.retranslate_ui()

    def _all_tabs(self):
        return self._tab_widgets

    def _current_tab(self):
        return self._tabs.currentWidget()

    def _on_config_saved(self) -> None:
        self._config_dirty = True
        reload_config()
        self._usage_tab.reload()

    def _apply(self) -> None:
        tab = self._current_tab()
        if hasattr(tab, "save") and tab.save():
            if tab is not self._interface_tab:
                self.config_changed.emit()

    def _accept(self) -> None:
        for tab in self._all_tabs():
            if tab.is_dirty() and not tab.save():
                return
        if self._config_dirty:
            self.config_changed.emit()
        self.accept()

    def _reject(self) -> None:
        for tab in self._all_tabs():
            if tab.is_dirty() and not tab.confirm_discard():
                return
        self.reject()
