from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_all_formatters
from quicklingo.config.rules_engine import preview_formatter, preset_rules_for_engine
from quicklingo.config.store import delete_formatter, save_formatter
from quicklingo.config.validation import ValidationError
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings.rule_builder_widget import RuleBuilderWidget

SAMPLE_TEXTS = {
    "дякую": "thanks / thank you\n\nExample: Thanks for your help!",
    "fine": (
        "──────────────────\n[1] fine\n→\nGood or acceptable.\n\nДобре.\n\n"
        "──────────────────\n[2] fine\n→\nHigh quality.\n\nЧудовий."
    ),
    "compel": (
        "compel\n→\nTo force someone to do something.\n\nЗмушувати, примушувати."
    ),
    "custom": "",
}

BUILTIN_PRESETS = [
    ("builtin:plain", "Plain text"),
    ("builtin:ua_en_cards", "UA→EN cards"),
    ("builtin:en_ua_cards", "EN→UA cards"),
]


class FormattersTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_id: str | None = None
        self._is_new = False

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
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("", "preset")
        self._mode_combo.addItem("", "rules")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._preset_combo = QComboBox()
        for engine, label in BUILTIN_PRESETS:
            self._preset_combo.addItem(label, engine)
        self._dup_preset_btn = QPushButton()
        self._dup_preset_btn.clicked.connect(self._duplicate_preset_to_rules)

        self._id_label = QLabel()
        self._name_label = QLabel()
        self._mode_label = QLabel()
        self._preset_label_row = QLabel()
        self._form.addRow(self._id_label, self._id_edit)
        self._form.addRow(self._name_label, self._name_edit)
        self._form.addRow(self._mode_label, self._mode_combo)
        self._form.addRow(self._preset_label_row, self._preset_combo)
        self._form.addRow("", self._dup_preset_btn)
        right_layout.addLayout(self._form)

        self._stack = QStackedWidget()
        self._preset_note = QLabel()
        self._rule_builder = RuleBuilderWidget()
        self._rule_builder._table.itemChanged.connect(lambda _: self.mark_dirty())
        self._stack.addWidget(self._preset_note)
        self._stack.addWidget(self._rule_builder)
        right_layout.addWidget(self._stack, stretch=1)

        preview_row = QHBoxLayout()
        self._sample_label = QLabel()
        self._sample_combo = QComboBox()
        for key in SAMPLE_TEXTS:
            self._sample_combo.addItem(key, key)
        self._sample_combo.currentIndexChanged.connect(self._update_preview)
        self._preview_btn = QPushButton()
        self._preview_btn.clicked.connect(self._update_preview)
        preview_row.addWidget(self._sample_label)
        preview_row.addWidget(self._sample_combo)
        preview_row.addWidget(self._preview_btn)
        right_layout.addLayout(preview_row)

        self._preview = QTextBrowser()
        self._preview.setMinimumHeight(120)
        right_layout.addWidget(self._preview)

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
        self._name_label.setText(tr("settings.formatters.name"))
        self._mode_label.setText(tr("settings.formatters.mode"))
        self._mode_combo.setItemText(0, tr("settings.formatters.mode_preset"))
        self._mode_combo.setItemText(1, tr("settings.formatters.mode_rules"))
        self._preset_label_row.setText(tr("settings.formatters.preset"))
        self._dup_preset_btn.setText(tr("settings.formatters.duplicate_to_rules"))
        self._preset_note.setText(tr("settings.formatters.preset_note"))
        self._sample_label.setText(tr("settings.formatters.sample"))
        self._preview_btn.setText(tr("settings.formatters.update_preview"))
        self._save_btn.setText(tr("settings.formatters.save"))
        self._rule_builder.retranslate_ui()

    def reload(self) -> None:
        current = self._current_id
        self._list.blockSignals(True)
        self._list.clear()
        for fmt in get_all_formatters():
            item = QListWidgetItem(fmt.name)
            item.setData(256, fmt.id)
            self._list.addItem(item)
        self._list.blockSignals(False)
        if current:
            for row in range(self._list.count()):
                if self._list.item(row).data(256) == current:
                    self._list.setCurrentRow(row)
                    return
        if self._list.count():
            self._list.setCurrentRow(0)
        self.mark_clean()

    def _on_mode_changed(self) -> None:
        is_rules = self._mode_combo.currentData() == "rules"
        self._stack.setCurrentIndex(1 if is_rules else 0)
        self.mark_dirty()

    def _on_select(self, row: int) -> None:
        if row < 0:
            return
        if not self.confirm_discard():
            self.reload()
            return
        fmt_id = self._list.item(row).data(256)
        fmt = next(f for f in get_all_formatters() if f.id == fmt_id)
        self._is_new = False
        self._current_id = fmt.id
        self._id_edit.setText(fmt.id)
        self._name_edit.setText(fmt.name)
        if fmt.engine.startswith("rules:v1"):
            self._mode_combo.setCurrentIndex(1)
            self._rule_builder.set_rules(fmt.rules or [{"type": "escape_plain"}])
        else:
            self._mode_combo.setCurrentIndex(0)
            idx = self._preset_combo.findData(fmt.engine)
            if idx >= 0:
                self._preset_combo.setCurrentIndex(idx)
        self._on_mode_changed()
        self._update_preview()
        self.mark_clean()

    def _add_new(self) -> None:
        if not self.confirm_discard():
            return
        self._is_new = True
        self._current_id = None
        self._id_edit.setText("new-formatter")
        self._name_edit.setText(tr("settings.formatters.new_name"))
        self._mode_combo.setCurrentIndex(0)
        self._preset_combo.setCurrentIndex(0)
        self._rule_builder.set_rules([{"type": "escape_plain"}])
        self._on_mode_changed()
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

    def _duplicate_preset_to_rules(self) -> None:
        engine = self._preset_combo.currentData()
        rules = preset_rules_for_engine(engine)
        self._mode_combo.setCurrentIndex(1)
        self._rule_builder.set_rules(rules)
        self._on_mode_changed()
        self.mark_dirty()

    def _update_preview(self) -> None:
        sample_key = self._sample_combo.currentData()
        text = SAMPLE_TEXTS.get(sample_key, "")
        if sample_key == "custom":
            text = "Hello\n→\nПривіт."
        engine, rules = self._current_engine_and_rules()
        try:
            html = preview_formatter(engine, rules, text)
        except Exception as exc:
            html = f"<pre>{exc}</pre>"
        self._preview.setHtml(html)

    def _current_engine_and_rules(self) -> tuple[str, list]:
        if self._mode_combo.currentData() == "rules":
            return "rules:v1", self._rule_builder.get_rules()
        return self._preset_combo.currentData(), []

    def _save_current(self) -> bool:
        engine, rules = self._current_engine_and_rules()
        try:
            save_formatter(
                id=self._id_edit.text().strip(),
                name=self._name_edit.text(),
                engine=engine,
                rules=rules if engine.startswith("rules:v1") else None,
                old_id=None if self._is_new else self._current_id,
            )
        except ValidationError as exc:
            self.show_error(self, str(exc))
            return False
        self._current_id = self._id_edit.text().strip()
        self._is_new = False
        self.reload()
        self.mark_clean()
        self.config_saved.emit()
        return True

    def _delete(self) -> None:
        if not self._current_id:
            return
        if not self.confirm_delete(
            tr("settings.formatters.delete_confirm", id=self._current_id)
        ):
            return
        try:
            delete_formatter(self._current_id)
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
