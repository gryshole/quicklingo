"""QSS and layout helpers for the settings dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QAction, QColor, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

TAB_CONTENT_MARGINS = (15, 15, 15, 15)
DIALOG_MARGINS = (12, 12, 12, 12)
GROUP_INNER_MARGINS = (0, 0, 0, 0)
API_KEY_HINT_LINK_COLOR = "#0076ff"

_EYE_ICON_CACHE: dict[bool, QIcon] = {}

TAB_CONTENT_MARGINS = (15, 15, 15, 15)
DIALOG_MARGINS = (12, 12, 12, 12)
GROUP_INNER_MARGINS = (0, 0, 0, 0)

SETTINGS_STYLE = """
QDialog#settingsDialog {
  background-color: #f8fafc;
}
QTabWidget::pane {
  border: 1px solid #e2e8f0;
  border-top: none;
  background: #ffffff;
  border-radius: 0 0 8px 8px;
  top: -1px;
}
QTabBar::tab {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-bottom: none;
  padding: 6px 12px;
  margin-right: 2px;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
  color: #475569;
  min-height: 20px;
}
QTabBar::tab:selected {
  background: #ffffff;
  color: #1e293b;
  font-weight: 600;
  border-bottom: 2px solid #2563eb;
}
QTabBar::tab:hover:!selected {
  background: #e8eef5;
  color: #334155;
}
QDialog#settingsDialog QGroupBox {
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-top: 25px;
  padding: 15px;
}
QDialog#settingsDialog QGroupBox::title {
  subcontrol-origin: margin;
  subcontrol-position: top left;
  top: 4px;
  left: 8px;
  background-color: transparent;
  color: #475569;
  font-weight: bold;
  font-size: 10pt;
}
QDialog#settingsDialog QComboBox,
QDialog#settingsDialog QLineEdit,
QDialog#settingsDialog QSpinBox,
QDialog#settingsDialog QPlainTextEdit {
  border: 1px solid #dcdcdc;
  border-radius: 6px;
  padding: 4px 8px;
  background-color: #ffffff;
  color: #1e293b;
  min-height: 28px;
}
QDialog#settingsDialog QComboBox:hover,
QDialog#settingsDialog QLineEdit:hover,
QDialog#settingsDialog QSpinBox:hover {
  border-color: #a0c4ff;
}
QDialog#settingsDialog QComboBox:focus,
QDialog#settingsDialog QLineEdit:focus,
QDialog#settingsDialog QSpinBox:focus {
  border-color: #3b82f6;
}
QDialog#settingsDialog QComboBox::drop-down {
  border: none;
  width: 22px;
}
QPushButton#btnOk {
  background-color: #0076ff;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 5px 15px;
  font-weight: 600;
  min-height: 32px;
  min-width: 72px;
}
QPushButton#btnOk:hover:enabled {
  background-color: #0066de;
}
QPushButton#btnApply,
QPushButton#btnCancel {
  background-color: #ffffff;
  color: #334155;
  border: 1px solid #dcdcdc;
  border-radius: 6px;
  padding: 5px 15px;
  min-height: 32px;
  min-width: 72px;
}
QPushButton#btnApply:hover:enabled,
QPushButton#btnCancel:hover:enabled {
  background-color: #f7f7f7;
  border-color: #a0c4ff;
}
QScrollArea {
  border: none;
  background: transparent;
}
QDialog#settingsDialog QScrollBar:vertical {
  background: #f5f5f5;
  width: 10px;
  margin: 2px 0;
  border-radius: 5px;
}
QDialog#settingsDialog QScrollBar::handle:vertical {
  background: #e0e0e0;
  min-height: 32px;
  border-radius: 5px;
}
QDialog#settingsDialog QScrollBar::handle:vertical:hover {
  background: #c8c8c8;
}
QDialog#settingsDialog QScrollBar::add-line:vertical,
QDialog#settingsDialog QScrollBar::sub-line:vertical {
  height: 0;
  border: none;
  background: none;
}
QDialog#settingsDialog QScrollBar::add-page:vertical,
QDialog#settingsDialog QScrollBar::sub-page:vertical {
  background: none;
}
QDialog#settingsDialog QLabel#apiKeyLabel {
  margin-top: 15px;
}
QDialog#settingsDialog QLabel#apiKeyHint {
  color: #64748b;
  font-size: 12px;
  margin-top: 10px;
  margin-bottom: 8px;
}
QDialog#settingsDialog QLabel#apiKeyNote {
  color: #64748b;
  font-size: 12px;
  margin-top: 12px;
}
QDialog#settingsDialog QLineEdit#apiKeyField {
  padding-right: 30px;
}
QDialog#settingsDialog QLineEdit#apiKeyField QToolButton {
  border: none;
  background: transparent;
  color: #94a3b8;
  padding: 2px 6px;
  min-width: 22px;
}
QDialog#settingsDialog QLineEdit#apiKeyField QToolButton:hover {
  color: #0076ff;
}
QDialog#settingsDialog QCheckBox {
  padding: 4px 0;
}
QDialog#settingsDialog QWidget#settingsTabBody {
  background-color: transparent;
}
QDialog#settingsDialog QWidget#settingsCard {
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
QDialog#settingsDialog QPlainTextEdit#promptFieldEdit {
  min-height: 70px;
  max-height: 90px;
  border: 1px solid #dcdcdc;
  border-radius: 6px;
  background-color: #ffffff;
  padding: 6px;
}
QDialog#settingsDialog QPushButton#btnPromptTemplate {
  background-color: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 3px 8px;
  color: #475569;
  font-size: 11px;
  min-height: 28px;
  max-height: 28px;
}
QDialog#settingsDialog QPushButton#btnPromptTemplate:hover:enabled {
  background-color: #f8fafc;
  border-color: #cbd5e1;
}
QDialog#settingsDialog QLabel#promptFieldLabel {
  color: #334155;
  font-weight: 600;
  padding-bottom: 2px;
}
QDialog#settingsDialog QListWidget#modelsList,
QDialog#settingsDialog QListWidget#directionsList,
QDialog#settingsDialog QListWidget#profilesList {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 5px;
  background-color: #ffffff;
  outline: none;
}
QDialog#settingsDialog QListWidget#modelsList::item,
QDialog#settingsDialog QListWidget#directionsList::item,
QDialog#settingsDialog QListWidget#profilesList::item {
  padding: 6px 10px;
  margin-bottom: 2px;
  border-radius: 4px;
}
QDialog#settingsDialog QListWidget#modelsList::item:selected,
QDialog#settingsDialog QListWidget#modelsList::item:selected:!active,
QDialog#settingsDialog QListWidget#directionsList::item:selected,
QDialog#settingsDialog QListWidget#directionsList::item:selected:!active,
QDialog#settingsDialog QListWidget#profilesList::item:selected,
QDialog#settingsDialog QListWidget#profilesList::item:selected:!active {
  background-color: #ebf5ff;
  color: #0056b3;
  font-weight: bold;
}
QDialog#settingsDialog QPushButton#btnModelsAction {
  border-radius: 6px;
  padding: 5px 12px;
  border: 1px solid #dcdcdc;
  background-color: #ffffff;
  color: #334155;
}
QDialog#settingsDialog QPushButton#btnModelsAction:hover:enabled {
  background-color: #f8fafc;
  border-color: #cbd5e1;
}
QDialog#settingsDialog QPushButton#btnModelsAction:disabled {
  color: #cbd5e1;
  border-color: #f1f5f9;
  background-color: #ffffff;
}
QDialog#settingsDialog QPushButton#btnModelsRemove {
  border-radius: 6px;
  padding: 5px 12px;
  border: 1px solid #dcdcdc;
  background-color: #ffffff;
  color: #334155;
}
QDialog#settingsDialog QPushButton#btnModelsRemove:hover:enabled {
  background-color: #fef2f2;
  color: #dc3545;
  border-color: #fca5a5;
}
QDialog#settingsDialog QPushButton#btnModelsRemove:disabled {
  color: #cbd5e1;
  border-color: #f1f5f9;
  background-color: #ffffff;
}
QDialog#settingsDialog QGroupBox#directionsFormGroup {
  margin-top: 0;
  padding: 20px;
  padding-top: 32px;
}
QDialog#settingsDialog QGroupBox#directionsFormGroup::title {
  top: 8px;
  left: 12px;
}
QDialog#settingsDialog QPushButton#btnDirectionsSave {
  background-color: #ffffff;
  border: 1px solid #0076ff;
  color: #0076ff;
  border-radius: 6px;
  padding: 6px 14px;
  font-weight: 600;
  min-height: 32px;
}
QDialog#settingsDialog QPushButton#btnDirectionsSave:hover:enabled {
  background-color: #0076ff;
  color: #ffffff;
}
QDialog#settingsDialog QGroupBox#profilesFormGroup {
  margin-top: 0;
  padding: 15px;
  padding-top: 32px;
}
QDialog#settingsDialog QGroupBox#profilesFormGroup::title {
  top: 8px;
  left: 12px;
}
QDialog#settingsDialog QGroupBox#profilesFormGroup QLineEdit,
QDialog#settingsDialog QGroupBox#profilesFormGroup QPlainTextEdit,
QDialog#settingsDialog QGroupBox#profilesFormGroup QComboBox {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 5px 8px;
  background-color: #ffffff;
  color: #1e293b;
}
QDialog#settingsDialog QGroupBox#profilesFormGroup QDoubleSpinBox {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 5px 24px 5px 8px;
  background-color: #ffffff;
  color: #1e293b;
  min-width: 100px;
}
QDialog#settingsDialog QGroupBox#profilesFormGroup QLineEdit:hover,
QDialog#settingsDialog QGroupBox#profilesFormGroup QPlainTextEdit:hover,
QDialog#settingsDialog QGroupBox#profilesFormGroup QComboBox:hover,
QDialog#settingsDialog QGroupBox#profilesFormGroup QDoubleSpinBox:hover {
  border-color: #94a3b8;
}
QDialog#settingsDialog QPushButton#btnProfilesSave {
  background-color: #ffffff;
  border: 1px solid #0076ff;
  color: #0076ff;
  border-radius: 6px;
  padding: 6px 14px;
  font-weight: bold;
  min-height: 32px;
}
QDialog#settingsDialog QPushButton#btnProfilesSave:hover:enabled {
  background-color: #ebf5ff;
  color: #0076ff;
  border-color: #0076ff;
}
QDialog#settingsDialog QPushButton#btnProfilesRemoveDirection {
  border-radius: 6px;
  padding: 5px 12px;
  border: 1px solid #dcdcdc;
  background-color: #ffffff;
  color: #334155;
}
QDialog#settingsDialog QPushButton#btnProfilesRemoveDirection:hover:enabled {
  background-color: #fef2f2;
  color: #dc3545;
  border-color: #fca5a5;
}
"""


def apply_settings_dialog_style(dialog: QWidget) -> None:
    dialog.setObjectName("settingsDialog")
    dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    dialog.setStyleSheet(SETTINGS_STYLE)


def configure_settings_dialog_buttons(
    apply_btn: QPushButton,
    button_box: QDialogButtonBox,
) -> None:
    apply_btn.setObjectName("btnApply")
    ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
    cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
    if ok_btn is not None:
        ok_btn.setObjectName("btnOk")
    if cancel_btn is not None:
        cancel_btn.setObjectName("btnCancel")


def apply_settings_tab_margins(tab: QWidget) -> None:
    layout = tab.layout()
    if layout is not None:
        layout.setContentsMargins(*TAB_CONTENT_MARGINS)


def configure_settings_tabs(tabs: QTabWidget) -> None:
    tabs.setDocumentMode(False)
    tabs.setUsesScrollButtons(True)


def configure_settings_card(card: QWidget) -> None:
    card.setObjectName("settingsCard")
    card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


def configure_prompt_reset_button(button: QPushButton) -> None:
    button.setObjectName("btnPromptTemplate")
    button.setFixedSize(130, 28)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


def configure_settings_group_box(group: QGroupBox) -> None:
    group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    layout = group.layout()
    if layout is None:
        return
    layout.setContentsMargins(*GROUP_INNER_MARGINS)
    if hasattr(layout, "setVerticalSpacing"):
        layout.setVerticalSpacing(10)
    if hasattr(layout, "setHorizontalSpacing"):
        layout.setHorizontalSpacing(10)


def align_form_labels(labels: list[QLabel], *, min_width: int = 0) -> None:
    if not labels:
        return
    metrics = QFontMetrics(labels[0].font())
    width = max(
        min_width,
        max(metrics.horizontalAdvance(label.text()) for label in labels),
    )
    for label in labels:
        label.setWordWrap(False)
        label.setFixedWidth(width)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


def style_api_key_hint_text(html: str) -> str:
    return html.replace(
        '<a href',
        f'<a style="color:{API_KEY_HINT_LINK_COLOR}; text-decoration:none;" href',
    )


def configure_api_key_label(label: QLabel, *, spaced: bool = True) -> None:
    if spaced:
        label.setObjectName("apiKeyLabel")


def configure_api_key_hint(label: QLabel) -> None:
    label.setObjectName("apiKeyHint")
    label.setWordWrap(False)
    label.setOpenExternalLinks(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def _eye_icon(*, visible: bool) -> QIcon:
    cached = _EYE_ICON_CACHE.get(visible)
    if cached is not None:
        return cached
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = QColor("#64748b")
    pen = QPen(color)
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawEllipse(QRectF(4.5, 6.0, 11.0, 8.0))
    painter.drawEllipse(QRectF(8.5, 8.5, 3.0, 3.0))
    if not visible:
        painter.drawLine(QPointF(5.0, 14.0), QPointF(15.0, 6.0))
    painter.end()
    icon = QIcon(pixmap)
    _EYE_ICON_CACHE[visible] = icon
    return icon


def configure_profiles_remove_direction_button(button: QPushButton) -> None:
    button.setObjectName("btnProfilesRemoveDirection")


def configure_profiles_tab_widgets(
    *,
    list_widget,
    add_btn: QPushButton,
    duplicate_btn: QPushButton,
    delete_btn: QPushButton,
    up_btn: QPushButton,
    down_btn: QPushButton,
    add_direction_btn: QPushButton,
    save_btn: QPushButton,
    form_group: QGroupBox,
) -> None:
    list_widget.setObjectName("profilesList")
    add_btn.setObjectName("btnModelsAction")
    duplicate_btn.setObjectName("btnModelsAction")
    delete_btn.setObjectName("btnModelsRemove")
    up_btn.setObjectName("btnModelsAction")
    down_btn.setObjectName("btnModelsAction")
    add_direction_btn.setObjectName("btnModelsAction")
    save_btn.setObjectName("btnProfilesSave")
    form_group.setObjectName("profilesFormGroup")


def configure_directions_tab_widgets(
    *,
    list_widget,
    add_btn: QPushButton,
    duplicate_btn: QPushButton,
    delete_btn: QPushButton,
    save_btn: QPushButton,
    form_group: QGroupBox,
) -> None:
    list_widget.setObjectName("directionsList")
    add_btn.setObjectName("btnModelsAction")
    duplicate_btn.setObjectName("btnModelsAction")
    delete_btn.setObjectName("btnModelsRemove")
    save_btn.setObjectName("btnDirectionsSave")
    form_group.setObjectName("directionsFormGroup")


def configure_models_tab_widgets(
    *,
    list_widget,
    add_btn: QPushButton,
    remove_btn: QPushButton,
    up_btn: QPushButton,
    down_btn: QPushButton,
    reset_btn: QPushButton,
) -> None:
    list_widget.setObjectName("modelsList")
    add_btn.setObjectName("btnModelsAction")
    up_btn.setObjectName("btnModelsAction")
    down_btn.setObjectName("btnModelsAction")
    reset_btn.setObjectName("btnModelsAction")
    remove_btn.setObjectName("btnModelsRemove")


def configure_password_field(line_edit: QLineEdit) -> None:
    line_edit.setObjectName("apiKeyField")
    line_edit.setEchoMode(QLineEdit.EchoMode.Password)
    toggle = QAction(_eye_icon(visible=False), "", line_edit)
    toggle.setCheckable(True)
    toggle.setToolTip("")

    def _sync_icon(checked: bool) -> None:
        line_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        toggle.setIcon(_eye_icon(visible=checked))

    toggle.toggled.connect(_sync_icon)
    line_edit.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)
