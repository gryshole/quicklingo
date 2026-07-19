from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_all_directions, get_all_profiles
from quicklingo.config.store import delete_direction, save_direction
from quicklingo.config.validation import ValidationError
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings_theme import (
    configure_directions_tab_widgets,
    configure_settings_group_box,
)


class DirectionsTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_id: str | None = None
        self._is_new = False

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter()
        root.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._add_btn = QPushButton()
        self._add_btn.clicked.connect(self._add_new)
        self._dup_btn = QPushButton()
        self._dup_btn.clicked.connect(self._duplicate)
        self._del_btn = QPushButton()
        self._del_btn.clicked.connect(self._delete)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._dup_btn)
        btn_row.addWidget(self._del_btn)
        left_layout.addLayout(btn_row)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._form_group = QGroupBox()
        self._form = QFormLayout(self._form_group)
        self._form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._form.setHorizontalSpacing(12)
        self._form.setVerticalSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.textChanged.connect(self.mark_dirty)
        self._label_edit = QLineEdit()
        self._label_edit.textChanged.connect(self.mark_dirty)
        self._source_edit = QLineEdit()
        self._source_edit.textChanged.connect(self.mark_dirty)
        self._target_edit = QLineEdit()
        self._target_edit.textChanged.connect(self.mark_dirty)
        self._default_profile = QComboBox()
        self._default_profile.currentIndexChanged.connect(self.mark_dirty)
        self._enabled = QCheckBox()
        self._enabled.stateChanged.connect(lambda _: self.mark_dirty())

        for field in (
            self._id_edit,
            self._label_edit,
            self._source_edit,
            self._target_edit,
            self._default_profile,
        ):
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._id_label = QLabel()
        self._label_label = QLabel()
        self._source_label = QLabel()
        self._target_label = QLabel()
        self._default_label = QLabel()

        self._form.addRow(self._id_label, self._id_edit)
        self._form.addRow(self._label_label, self._label_edit)
        self._form.addRow(self._source_label, self._source_edit)
        self._form.addRow(self._target_label, self._target_edit)
        self._form.addRow(self._default_label, self._default_profile)
        self._form.addRow(self._enabled)

        self._save_btn = QPushButton()
        self._save_btn.clicked.connect(self._save_current)
        save_row = QHBoxLayout()
        save_row.setContentsMargins(0, 8, 0, 0)
        save_row.addStretch()
        save_row.addWidget(self._save_btn)
        save_wrap = QWidget()
        save_wrap.setLayout(save_row)
        self._form.addRow(save_wrap)

        configure_settings_group_box(self._form_group)
        configure_directions_tab_widgets(
            list_widget=self._list,
            add_btn=self._add_btn,
            duplicate_btn=self._dup_btn,
            delete_btn=self._del_btn,
            save_btn=self._save_btn,
            form_group=self._form_group,
        )
        right_layout.addWidget(self._form_group)
        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.retranslate_ui()
        self.reload()

    def retranslate_ui(self) -> None:
        self._add_btn.setText(tr("common.add"))
        self._dup_btn.setText(tr("common.duplicate"))
        self._del_btn.setText(tr("common.delete"))
        self._form_group.setTitle(tr("settings.directions.group"))
        self._id_label.setText(tr("common.id"))
        self._label_label.setText(tr("settings.directions.label"))
        self._source_label.setText(tr("settings.directions.source_lang"))
        self._target_label.setText(tr("settings.directions.target_lang"))
        self._default_label.setText(tr("settings.directions.default_profile"))
        self._enabled.setText(tr("settings.directions.enabled"))
        self._save_btn.setText(tr("settings.directions.save"))
        self._populate_list()

    def reload(self) -> None:
        self._populate_list()
        self._refresh_profile_combo()
        if self._list.count() and self._list.currentRow() < 0:
            self._list.setCurrentRow(0)
        self.mark_clean()

    def _populate_list(self) -> None:
        current = self._current_id
        self._list.blockSignals(True)
        self._list.clear()
        for direction in get_all_directions():
            suffix = "" if direction.enabled else tr("settings.directions.disabled_suffix")
            item = QListWidgetItem(f"{direction.label}{suffix}")
            item.setData(256, direction.id)
            self._list.addItem(item)
        self._list.blockSignals(False)
        if current:
            for row in range(self._list.count()):
                if self._list.item(row).data(256) == current:
                    self._list.setCurrentRow(row)
                    return

    def _refresh_profile_combo(self) -> None:
        current = self._default_profile.currentData()
        self._default_profile.blockSignals(True)
        self._default_profile.clear()
        for profile in get_all_profiles():
            self._default_profile.addItem(profile.name, profile.id)
        if current:
            idx = self._default_profile.findData(current)
            if idx >= 0:
                self._default_profile.setCurrentIndex(idx)
        self._default_profile.blockSignals(False)

    def _on_select(self, row: int) -> None:
        if row < 0:
            return
        if not self.confirm_discard():
            self.reload()
            return
        item = self._list.item(row)
        direction_id = item.data(256)
        direction = next(d for d in get_all_directions() if d.id == direction_id)
        self._is_new = False
        self._current_id = direction.id
        self._id_edit.setText(direction.id)
        self._label_edit.setText(direction.label)
        self._source_edit.setText(direction.source_lang)
        self._target_edit.setText(direction.target_lang)
        idx = self._default_profile.findData(direction.default_profile)
        if idx >= 0:
            self._default_profile.setCurrentIndex(idx)
        self._enabled.setChecked(direction.enabled)
        self.mark_clean()

    def _add_new(self) -> None:
        if not self.confirm_discard():
            return
        self._is_new = True
        self._current_id = None
        self._id_edit.setText("new-direction")
        self._label_edit.setText(tr("settings.directions.new_label"))
        self._source_edit.setText("")
        self._target_edit.setText("")
        if self._default_profile.count():
            self._default_profile.setCurrentIndex(0)
        self._enabled.setChecked(True)
        self.mark_dirty()

    def _duplicate(self) -> None:
        if self._list.currentRow() < 0:
            return
        if not self.confirm_discard():
            return
        self._is_new = True
        self._current_id = None
        base_id = self._id_edit.text().strip() or "direction"
        self._id_edit.setText(f"{base_id}-copy")
        self._label_edit.setText(self._label_edit.text() + tr("common.copy_suffix"))
        self.mark_dirty()

    def _save_current(self) -> bool:
        try:
            save_direction(
                id=self._id_edit.text().strip(),
                label=self._label_edit.text(),
                source_lang=self._source_edit.text(),
                target_lang=self._target_edit.text(),
                default_profile=self._default_profile.currentData(),
                enabled=self._enabled.isChecked(),
                old_id=None if self._is_new else self._current_id,
            )
        except ValidationError as exc:
            self.show_error(self, str(exc))
            return False
        self._current_id = self._id_edit.text().strip()
        self._is_new = False
        self._populate_list()
        self.mark_clean()
        self.config_saved.emit()
        return True

    def _delete(self) -> None:
        if self._list.currentRow() < 0 or not self._current_id:
            return
        if not self.confirm_delete(
            tr("settings.directions.delete_confirm", id=self._current_id)
        ):
            return
        try:
            delete_direction(self._current_id)
        except ValidationError as exc:
            self.show_error(self, str(exc))
            return
        self._current_id = None
        self.reload()
        self.config_saved.emit()

    def save(self) -> bool:
        if self.is_dirty():
            return self._save_current()
        return True
