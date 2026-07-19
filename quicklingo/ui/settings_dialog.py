from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
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
from quicklingo.ui.settings.interface_tab import InterfaceTab
from quicklingo.ui.settings.learning_features_tab import LearningFeaturesTab
from quicklingo.ui.settings.models_tab import ModelsTab
from quicklingo.ui.settings.profiles_tab import ProfilesTab
from quicklingo.ui.settings.sync_tab import SyncTab
from quicklingo.ui.settings_theme import (
    DIALOG_MARGINS,
    apply_settings_dialog_style,
    apply_settings_tab_margins,
    configure_settings_dialog_buttons,
    configure_settings_tabs,
)
from quicklingo.ui.window_state import restore_window_geometry, save_window_geometry


class SettingsDialog(QDialog):
    config_changed = Signal()
    api_keys_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        apply_settings_dialog_style(self)
        restore_window_geometry(self, "settings", default_width=860, default_height=725)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_MARGINS)
        layout.setSpacing(10)
        self._tabs = QTabWidget()
        configure_settings_tabs(self._tabs)

        self._interface_tab = InterfaceTab()
        self._api_keys_tab = ApiKeysTab()
        self._models_tab = ModelsTab()
        self._features_tab = FeaturesTab()
        self._learning_features_tab = LearningFeaturesTab()
        self._sync_tab = SyncTab()
        self._directions_tab = DirectionsTab()
        self._profiles_tab = ProfilesTab()

        self._tab_widgets = (
            self._interface_tab,
            self._api_keys_tab,
            self._models_tab,
            self._features_tab,
            self._learning_features_tab,
            self._sync_tab,
            self._directions_tab,
            self._profiles_tab,
        )
        for tab in self._tab_widgets:
            apply_settings_tab_margins(tab)

        layout.addWidget(self._tabs)

        for tab in self._tab_widgets:
            if tab not in (self._interface_tab, self._features_tab, self._learning_features_tab):
                tab.config_saved.connect(self._on_config_saved)
        self._api_keys_tab.api_keys_saved.connect(self.api_keys_changed.emit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._apply_btn = QPushButton()
        self._apply_btn.clicked.connect(self._apply)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        configure_settings_dialog_buttons(self._apply_btn, self._buttons)
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
        self._tabs.addTab(self._learning_features_tab, tr("settings.tab_learning"))
        self._tabs.addTab(self._sync_tab, tr("settings.tab_sync"))
        self._tabs.addTab(self._directions_tab, tr("settings.tab_directions"))
        self._tabs.addTab(self._profiles_tab, tr("settings.tab_profiles"))
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

    def closeEvent(self, event: QCloseEvent) -> None:
        save_window_geometry(self, "settings")
        super().closeEvent(event)
