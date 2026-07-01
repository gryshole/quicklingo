from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from quicklingo.i18n import tr


class TagWizardDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        visible_count: int,
        selected_count: int,
        known_tags: list[str],
    ) -> None:
        super().__init__(parent)
        self._visible_count = visible_count
        self._selected_count = selected_count
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        self._scope_group_box = QGroupBox()
        scope_layout = QVBoxLayout(self._scope_group_box)
        self._scope_visible = QRadioButton()
        self._scope_selected = QRadioButton()
        self._scope_group = QButtonGroup(self)
        self._scope_group.addButton(self._scope_visible, 0)
        self._scope_group.addButton(self._scope_selected, 1)
        if selected_count > 0:
            self._scope_selected.setChecked(True)
        else:
            self._scope_visible.setChecked(True)
            self._scope_selected.setEnabled(False)
        scope_layout.addWidget(self._scope_visible)
        scope_layout.addWidget(self._scope_selected)
        layout.addWidget(self._scope_group_box)

        self._action_group_box = QGroupBox()
        action_layout = QVBoxLayout(self._action_group_box)
        self._action_add = QRadioButton()
        self._action_replace = QRadioButton()
        self._action_remove = QRadioButton()
        self._action_group = QButtonGroup(self)
        self._action_group.addButton(self._action_add, 0)
        self._action_group.addButton(self._action_replace, 1)
        self._action_group.addButton(self._action_remove, 2)
        self._action_add.setChecked(True)
        action_layout.addWidget(self._action_add)
        action_layout.addWidget(self._action_replace)
        action_layout.addWidget(self._action_remove)
        layout.addWidget(self._action_group_box)

        tags_row = QHBoxLayout()
        self._tags_field = QLineEdit()
        self._known_combo = QComboBox()
        self._known_combo.addItem("", "")
        for tag in known_tags:
            self._known_combo.addItem(tag, tag)
        self._pick_btn = QPushButton()
        self._pick_btn.clicked.connect(self._append_known_tag)
        tags_row.addWidget(self._tags_field, stretch=1)
        tags_row.addWidget(self._known_combo)
        tags_row.addWidget(self._pick_btn)
        layout.addLayout(tags_row)

        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        layout.addWidget(self._preview_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._scope_group.buttonClicked.connect(self._update_preview)
        self._action_group.buttonClicked.connect(self._update_preview)
        self._tags_field.textChanged.connect(self._update_preview)
        self.retranslate_ui()
        self._update_preview()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("history.tag_wizard_title"))
        self._scope_group_box.setTitle(tr("history.tag_wizard_scope_group"))
        self._action_group_box.setTitle(tr("history.tag_wizard_action_group"))
        self._scope_visible.setText(
            tr("history.tag_wizard_scope_visible", count=self._visible_count)
        )
        self._scope_selected.setText(
            tr("history.tag_wizard_scope_selected", count=self._selected_count)
        )
        self._action_add.setText(tr("history.tag_wizard_action_add"))
        self._action_replace.setText(tr("history.tag_wizard_action_replace"))
        self._action_remove.setText(tr("history.tag_wizard_action_remove"))
        self._pick_btn.setText(tr("history.tag_wizard_pick"))
        self._update_preview()

    def _append_known_tag(self) -> None:
        tag = self._known_combo.currentData()
        if not tag:
            return
        current = self._tags_field.text().strip()
        parts = [part.strip() for part in current.split(",") if part.strip()]
        if tag not in parts:
            parts.append(tag)
        self._tags_field.setText(", ".join(parts))

    def _target_count(self) -> int:
        if self._scope_selected.isChecked() and self._selected_count > 0:
            return self._selected_count
        return self._visible_count

    def _update_preview(self) -> None:
        count = self._target_count()
        action = self._action_key()
        if action == "replace":
            action_label = tr("history.tag_wizard_action_replace_short")
        elif action == "remove":
            action_label = tr("history.tag_wizard_action_remove_short")
        else:
            action_label = tr("history.tag_wizard_action_add_short")
        self._preview_label.setText(
            tr("history.tag_wizard_confirm", count=count, action=action_label)
        )

    def _action_key(self) -> str:
        if self._action_replace.isChecked():
            return "replace"
        if self._action_remove.isChecked():
            return "remove"
        return "add"

    def use_selected_scope(self) -> bool:
        return self._scope_selected.isChecked() and self._selected_count > 0

    def parsed_tags(self) -> list[str]:
        return [part.strip() for part in self._tags_field.text().split(",") if part.strip()]

    def action_key(self) -> str:
        return self._action_key()
