from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QVBoxLayout

from quicklingo import settings
from quicklingo.config.loader import get_directions, get_profiles_for_direction
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab


class UsageTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._outer_layout = QVBoxLayout(self)
        self._group: QGroupBox | None = None
        self._combos: dict[str, QComboBox] = {}
        self._build_form()
        self._outer_layout.addStretch()

    def _build_form(self) -> None:
        if self._group is not None:
            self._outer_layout.removeWidget(self._group)
            self._group.deleteLater()
        self._combos.clear()
        self._group = QGroupBox()
        form = QFormLayout(self._group)
        for direction in get_directions():
            combo = QComboBox()
            for profile in get_profiles_for_direction(direction.id):
                combo.addItem(profile.name, profile.id)
            active = settings.get_active_profile(direction.id)
            index = combo.findData(active)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(self.mark_dirty)
            form.addRow(f"{direction.label}:", combo)
            self._combos[direction.id] = combo
        self._outer_layout.insertWidget(0, self._group)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        if self._group:
            self._group.setTitle(tr("settings.usage.group"))

    def reload(self) -> None:
        self._build_form()
        self.mark_clean()

    def save(self) -> bool:
        active_profiles = {
            direction_id: combo.currentData()
            for direction_id, combo in self._combos.items()
        }
        settings.save_active_profiles(active_profiles)
        self.mark_clean()
        self.config_saved.emit()
        return True
