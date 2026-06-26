from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_all_directions, get_all_formatters, get_all_profiles
from quicklingo.config.store import delete_profile, read_prompt_body, save_profile
from quicklingo.config.validation import ValidationError
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab


class ProfilesTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_id: str | None = None
        self._is_new = False
        self._direction_widgets: dict[str, dict] = {}

        root = QHBoxLayout(self)
        splitter = QSplitter()
        root.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._list)
        btn_row = QHBoxLayout()
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
        self._form = QFormLayout()
        self._id_edit = QLineEdit()
        self._id_edit.textChanged.connect(self.mark_dirty)
        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self.mark_dirty)
        self._desc_edit = QLineEdit()
        self._desc_edit.textChanged.connect(self.mark_dirty)
        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.valueChanged.connect(lambda _: self.mark_dirty())

        self._id_label = QLabel()
        self._name_label = QLabel()
        self._desc_label = QLabel()
        self._temp_label = QLabel()
        self._form.addRow(self._id_label, self._id_edit)
        self._form.addRow(self._name_label, self._name_edit)
        self._form.addRow(self._desc_label, self._desc_edit)
        self._form.addRow(self._temp_label, self._temperature)
        right_layout.addLayout(self._form)

        dir_row = QHBoxLayout()
        self._direction_label = QLabel()
        self._add_direction_combo = QComboBox()
        self._add_dir_btn = QPushButton()
        self._add_dir_btn.clicked.connect(self._add_direction)
        dir_row.addWidget(self._direction_label)
        dir_row.addWidget(self._add_direction_combo, stretch=1)
        dir_row.addWidget(self._add_dir_btn)
        right_layout.addLayout(dir_row)

        self._dir_tabs = QTabWidget()
        right_layout.addWidget(self._dir_tabs, stretch=1)

        self._save_btn = QPushButton()
        self._save_btn.clicked.connect(self._save_current)
        right_layout.addWidget(self._save_btn)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        self.retranslate_ui()
        self.reload()

    def retranslate_ui(self) -> None:
        self._add_btn.setText(tr("common.add"))
        self._dup_btn.setText(tr("common.duplicate"))
        self._del_btn.setText(tr("common.delete"))
        self._id_label.setText(tr("common.id"))
        self._name_label.setText(tr("settings.profiles.name"))
        self._desc_label.setText(tr("settings.profiles.description"))
        self._temp_label.setText(tr("settings.profiles.temperature"))
        self._direction_label.setText(tr("settings.profiles.direction"))
        self._add_dir_btn.setText(tr("settings.profiles.add_direction"))
        self._save_btn.setText(tr("settings.profiles.save"))
        for direction_id, widgets in self._direction_widgets.items():
            widgets["prompt_label"].setText(tr("settings.profiles.prompt"))
            widgets["remove_btn"].setText(tr("settings.profiles.remove_direction"))
            formatter_label = widgets.get("formatter_label")
            if formatter_label:
                formatter_label.setText(tr("settings.profiles.formatter"))

    def reload(self) -> None:
        self._populate_list()
        self._refresh_add_direction_combo()
        if self._list.count() and self._list.currentRow() < 0:
            self._list.setCurrentRow(0)
        self.mark_clean()

    def _populate_list(self) -> None:
        current = self._current_id
        self._list.blockSignals(True)
        self._list.clear()
        for profile in get_all_profiles():
            item = QListWidgetItem(profile.name)
            item.setData(256, profile.id)
            self._list.addItem(item)
        self._list.blockSignals(False)
        if current:
            for row in range(self._list.count()):
                if self._list.item(row).data(256) == current:
                    self._list.setCurrentRow(row)
                    return

    def _refresh_add_direction_combo(self) -> None:
        mapped = set(self._direction_widgets)
        self._add_direction_combo.clear()
        for direction in get_all_directions():
            if direction.id not in mapped:
                self._add_direction_combo.addItem(direction.label, direction.id)

    def _clear_direction_tabs(self) -> None:
        self._dir_tabs.clear()
        self._direction_widgets.clear()

    def _build_direction_tab(
        self, direction_id: str, label: str, prompt: str, formatter_id: str
    ) -> None:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        prompt_label = QLabel()
        prompt_edit = QPlainTextEdit()
        prompt_edit.setPlainText(prompt)
        prompt_edit.textChanged.connect(self.mark_dirty)
        formatter_combo = QComboBox()
        for fmt in get_all_formatters():
            formatter_combo.addItem(fmt.name, fmt.id)
        idx = formatter_combo.findData(formatter_id)
        if idx >= 0:
            formatter_combo.setCurrentIndex(idx)
        elif formatter_combo.count():
            formatter_combo.setCurrentIndex(0)
        formatter_combo.currentIndexChanged.connect(lambda _: self.mark_dirty())
        remove_btn = QPushButton()
        remove_btn.clicked.connect(lambda: self._remove_direction(direction_id))
        prompt_label.setText(tr("settings.profiles.prompt"))
        layout.addWidget(prompt_label)
        layout.addWidget(prompt_edit, stretch=1)
        form = QFormLayout()
        formatter_label = QLabel(tr("settings.profiles.formatter"))
        form.addRow(formatter_label, formatter_combo)
        layout.addLayout(form)
        remove_btn.setText(tr("settings.profiles.remove_direction"))
        layout.addWidget(remove_btn)
        self._dir_tabs.addTab(widget, label)
        self._direction_widgets[direction_id] = {
            "prompt": prompt_edit,
            "formatter": formatter_combo,
            "prompt_label": prompt_label,
            "formatter_label": formatter_label,
            "remove_btn": remove_btn,
            "tab_label": label,
        }

    def _on_select(self, row: int) -> None:
        if row < 0:
            return
        if not self.confirm_discard():
            self.reload()
            return
        profile_id = self._list.item(row).data(256)
        profile = next(p for p in get_all_profiles() if p.id == profile_id)
        self._is_new = False
        self._current_id = profile.id
        self._id_edit.setText(profile.id)
        self._name_edit.setText(profile.name)
        self._desc_edit.setText(profile.description)
        self._temperature.setValue(profile.temperature)
        self._clear_direction_tabs()
        for direction in get_all_directions():
            if direction.id not in profile.prompts:
                continue
            body = read_prompt_body(profile.id, direction.id)
            if not body:
                body = profile.prompts.get(direction.id, "")
            fmt_id = profile.formatters.get(direction.id, "")
            self._build_direction_tab(direction.id, direction.label, body, fmt_id)
        self._refresh_add_direction_combo()
        self.mark_clean()

    def _add_new(self) -> None:
        if not self.confirm_discard():
            return
        self._is_new = True
        self._current_id = None
        self._id_edit.setText("new-profile")
        self._name_edit.setText(tr("settings.profiles.new_name"))
        self._desc_edit.setText("")
        self._temperature.setValue(0.2)
        self._clear_direction_tabs()
        directions = get_all_directions()
        if directions:
            d = directions[0]
            self._build_direction_tab(d.id, d.label, "You are a translation assistant.\n", "")
        self._refresh_add_direction_combo()
        self.mark_dirty()

    def _duplicate(self) -> None:
        if self._list.currentRow() < 0:
            return
        if not self.confirm_discard():
            return
        self._is_new = True
        self._current_id = None
        self._id_edit.setText(f"{self._id_edit.text().strip()}-copy")
        self._name_edit.setText(self._name_edit.text() + tr("common.copy_suffix"))
        self.mark_dirty()

    def _add_direction(self) -> None:
        direction_id = self._add_direction_combo.currentData()
        if not direction_id:
            return
        direction = next(d for d in get_all_directions() if d.id == direction_id)
        self._build_direction_tab(direction.id, direction.label, "", "")
        self._refresh_add_direction_combo()
        self.mark_dirty()

    def _remove_direction(self, direction_id: str) -> None:
        if len(self._direction_widgets) <= 1:
            self.show_error(self, tr("settings.profiles.need_one_direction"))
            return
        tab_label = self._direction_widgets[direction_id]["tab_label"]
        for i in range(self._dir_tabs.count()):
            if self._dir_tabs.tabText(i) == tab_label:
                self._dir_tabs.removeTab(i)
                break
        self._direction_widgets.pop(direction_id, None)
        self._refresh_add_direction_combo()
        self.mark_dirty()

    def _save_current(self) -> bool:
        if not self._direction_widgets:
            self.show_error(self, tr("settings.profiles.add_one_direction"))
            return False
        prompts = {
            did: w["prompt"].toPlainText()
            for did, w in self._direction_widgets.items()
        }
        formatters = {
            did: w["formatter"].currentData()
            for did, w in self._direction_widgets.items()
        }
        try:
            save_profile(
                id=self._id_edit.text().strip(),
                name=self._name_edit.text(),
                description=self._desc_edit.text(),
                temperature=self._temperature.value(),
                direction_prompts=prompts,
                direction_formatters=formatters,
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
        if not self._current_id:
            return
        if not self.confirm_delete(
            tr("settings.profiles.delete_confirm", id=self._current_id)
        ):
            return
        try:
            delete_profile(self._current_id)
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
