"""Shared Quiz-style palette and QSS for the main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics, QColor, QPalette
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

APP_BG = "#f8fafc"
CARD_BG = "#ffffff"
CARD_BORDER = "#e2e8f0"
TEXT_PRIMARY = "#1e293b"
TEXT_LABEL = "#334155"
TEXT_MUTED = "#64748b"
PLACEHOLDER_MUTED = "#9ca3af"
PRIMARY = "#2563eb"
PRIMARY_DARK = "#1e40af"
INPUT_BORDER = "#cbd5e1"
BORDER_HOVER = "#a0c4ff"
HOVER_BTN_BG = "#f7f7f7"
ERROR = "#dc2626"
RADIUS_CARD = "12px"
RADIUS_CONTROL = "8px"

SETTINGS_LABEL_WIDTH = 108  # fallback until labels are measured
SETTINGS_FORM_LABEL_MIN_WIDTH = 72
COMPACT_ROW_SPACING = 8
COMPACT_SECTION_SPACING = 6
COMPACT_SECTION_MARGINS = (12, 12, 12, 12)
SETTINGS_CONTROL_HEIGHT = 28
SETTINGS_FONT_PT = 10

_CHEVRON_PNG = Path(__file__).resolve().parent / "assets" / "chevron_down.png"


def _ensure_chevron_png() -> Path:
    if _CHEVRON_PNG.exists():
        return _CHEVRON_PNG

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QGuiApplication, QColor, QPainter, QPen, QPixmap

    if QGuiApplication.instance() is None:
        raise RuntimeError("QApplication must exist before building combo chevron icon")

    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(TEXT_MUTED))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(QPointF(6, 8), QPointF(10, 12))
    painter.drawLine(QPointF(10, 12), QPointF(14, 8))
    painter.end()

    _CHEVRON_PNG.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(_CHEVRON_PNG), "PNG")
    return _CHEVRON_PNG


def _chevron_qss_url() -> str:
    return _ensure_chevron_png().as_posix().replace("\\", "/")


def _combo_down_arrow_qss(*selectors: str) -> str:
    url = _chevron_qss_url()
    rules = []
    for selector in selectors:
        rules.append(
            f"{selector}::down-arrow {{"
            f' image: url("{url}");'
            " width: 16px;"
            " height: 16px;"
            " border: none;"
            " background: transparent;"
            " }"
        )
    return "\n".join(rules)

APP_BACKGROUND_STYLE = f"QWidget#appRoot {{ background: {APP_BG}; }}"

CARD_STYLE = (
    f"QWidget#settingsCard, QWidget#inputCard, QWidget#resultCard {{"
    f" background: {CARD_BG}; border: 1px solid {CARD_BORDER};"
    f" border-radius: {RADIUS_CARD}; }}"
)

SECTION_TITLE_STYLE = (
    "color: #666666; font-size: 9pt;"
    " font-weight: 600; letter-spacing: 1.2px; margin-bottom: 8px;"
)

COMPACT_FORM_LABEL_STYLE = (
    f"color: {TEXT_MUTED}; font-size: {SETTINGS_FONT_PT}pt; font-weight: normal;"
)


def settings_ui_font(family: str | None = None) -> QFont:
    font = QFont(family) if family else QFont()
    font.setPointSize(SETTINGS_FONT_PT)
    return font


def ensure_valid_point_font(widget: QWidget) -> QFont:
    """QSS pixel font sizes leave pointSize at -1; normalize before Qt uses it."""
    font = QFont(widget.font())
    if font.pointSize() <= 0:
        if font.pixelSize() > 0:
            font.setPointSize(max(1, round(font.pixelSize() * 0.75)))
        else:
            font.setPointSize(SETTINGS_FONT_PT)
        widget.setFont(font)
    return font


def disable_combo_popup_animation(app) -> None:
    """Windows animates combo popups with alpha; content underneath shows through."""
    try:
        app.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo, False)
    except (AttributeError, TypeError):
        pass


def _opaque_combo_popup_view(combo: QComboBox) -> None:
    view = combo.view()
    if view is None:
        return
    view.setAutoFillBackground(True)
    view.setFrameShape(QFrame.Shape.NoFrame)
    palette = view.palette()
    bg = QColor(CARD_BG)
    for role in (
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Window,
        QPalette.ColorRole.Button,
    ):
        palette.setColor(role, bg)
    view.setPalette(palette)


def _opaque_combo_popup_window(combo: QComboBox) -> None:
    view = combo.view()
    if view is None:
        return
    popup = view.window()
    if popup is None or popup is combo:
        return
    popup.setAutoFillBackground(True)
    popup.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
    palette = popup.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(CARD_BG))
    popup.setPalette(palette)


def apply_combo_font(combo: QComboBox) -> None:
    """Ensure combo, popup list, and line edit use a valid point-size font."""
    if getattr(combo, "_ql_combo_font_patched", False):
        return

    font = settings_ui_font(combo.font().family())
    combo.setFont(font)
    view = combo.view()
    if view is not None:
        view.setFont(font)
    _opaque_combo_popup_view(combo)
    line_edit = combo.lineEdit()
    if line_edit is not None:
        line_edit.setFont(font)

    original_show_popup = combo.showPopup

    def show_popup_with_font() -> None:
        ensure_valid_point_font(combo)
        popup_view = combo.view()
        if popup_view is not None:
            popup_view.setFont(settings_ui_font(combo.font().family()))
        _opaque_combo_popup_window(combo)
        original_show_popup()
        _opaque_combo_popup_window(combo)

    combo.showPopup = show_popup_with_font  # type: ignore[method-assign]
    combo._ql_combo_font_patched = True


def _settings_combo_style() -> str:
    return f"""
QWidget#settingsCard QComboBox {{
  background: {CARD_BG};
  border: 1px solid {INPUT_BORDER};
  border-radius: 6px;
  padding: 0 24px 0 8px;
  min-height: {SETTINGS_CONTROL_HEIGHT}px;
  max-height: {SETTINGS_CONTROL_HEIGHT}px;
  color: {TEXT_PRIMARY};
  font-size: {SETTINGS_FONT_PT}pt;
}}
QWidget#settingsCard QComboBox:hover {{
  border: 1px solid {BORDER_HOVER};
}}
QWidget#settingsCard QComboBox:focus, QWidget#settingsCard QComboBox:on {{
  border-color: {PRIMARY};
}}
QWidget#settingsCard QComboBox QAbstractItemView,
QWidget#settingsCard QComboBox QListView {{
  border: 1px solid {INPUT_BORDER};
  border-radius: 6px;
  background-color: {CARD_BG};
  outline: none;
  font-size: {SETTINGS_FONT_PT}pt;
  selection-background-color: #eff6ff;
  selection-color: {PRIMARY_DARK};
}}
QWidget#settingsCard QComboBox::drop-down {{
  subcontrol-origin: padding;
  subcontrol-position: center right;
  width: 24px;
  border: none;
  background: transparent;
}}
{_combo_down_arrow_qss("QWidget#settingsCard QComboBox")}
QWidget#settingsCard QComboBox QLineEdit {{
  padding: 0 2px 0 0;
  min-height: {SETTINGS_CONTROL_HEIGHT - 4}px;
  max-height: {SETTINGS_CONTROL_HEIGHT - 4}px;
  font-size: {SETTINGS_FONT_PT}pt;
  border: none;
  background: transparent;
}}
"""


def _combo_style() -> str:
    return f"""
QComboBox {{
  background: {CARD_BG};
  border: 1px solid {INPUT_BORDER};
  border-radius: {RADIUS_CONTROL};
  padding: 6px 28px 6px 10px;
  min-height: 32px;
  color: {TEXT_PRIMARY};
  font-size: {SETTINGS_FONT_PT}pt;
}}
QComboBox:hover {{
  border: 1px solid {BORDER_HOVER};
}}
QComboBox:focus, QComboBox:on {{
  border-color: {PRIMARY};
}}
QComboBox::drop-down {{
  subcontrol-origin: padding;
  subcontrol-position: center right;
  width: 24px;
  border: none;
  background: transparent;
}}
{_combo_down_arrow_qss("QComboBox")}
QComboBox QAbstractItemView,
QComboBox QListView {{
  border: 1px solid {INPUT_BORDER};
  border-radius: {RADIUS_CONTROL};
  background-color: {CARD_BG};
  outline: none;
  font-size: {SETTINGS_FONT_PT}pt;
  selection-background-color: #eff6ff;
  selection-color: {PRIMARY_DARK};
}}
"""

OUTPUT_FIELD_STYLE = """
QWidget#resultCard QTextEdit {
  border: none;
  background: transparent;
  padding: 0;
}
"""

INPUT_STYLE = f"""
QTextEdit#mainInput, QLineEdit#mainInput {{
  background: {CARD_BG};
  border: 1px solid {INPUT_BORDER};
  border-radius: {RADIUS_CONTROL};
  padding: 10px 12px;
  color: {TEXT_PRIMARY};
  font-size: 11pt;
}}
QTextEdit#mainInput:hover, QLineEdit#mainInput:hover {{
  border: 1px solid {BORDER_HOVER};
}}
QTextEdit#mainInput:focus, QLineEdit#mainInput:focus {{
  border-color: {PRIMARY};
}}
"""

OUTPUT_PLACEHOLDER_STYLE = (
    f"color: {PLACEHOLDER_MUTED}; font-size: 10pt; background: transparent;"
)

SEGMENTED_STYLE = f"""
QWidget#segmentedControl {{
  background: transparent;
  border: none;
}}
QWidget#settingsCard QWidget#segmentedControl {{
  max-height: {SETTINGS_CONTROL_HEIGHT}px;
}}
QWidget#segmentedControl QPushButton {{
  background: transparent;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  color: {TEXT_LABEL};
  font-weight: 500;
  font-size: {SETTINGS_FONT_PT}pt;
  min-height: {SETTINGS_CONTROL_HEIGHT}px;
  max-height: {SETTINGS_CONTROL_HEIGHT}px;
}}
QWidget#segmentedControl QPushButton:checked {{
  background-color: #EBF5FF;
  color: #0056b3;
  font-weight: 600;
}}
QWidget#segmentedControl QPushButton:hover:!checked {{
  background: transparent;
  color: {TEXT_PRIMARY};
}}
QWidget#segmentedControl QPushButton:disabled {{
  color: #94a3b8;
}}
"""

SECONDARY_BTN_STYLE = f"""
QPushButton {{
  background: {CARD_BG};
  border: 1px solid {INPUT_BORDER};
  border-radius: {RADIUS_CONTROL};
  padding: 6px 12px;
  color: {TEXT_LABEL};
  min-height: 28px;
}}
QPushButton:hover {{
  background-color: {HOVER_BTN_BG};
  border: 1px solid {BORDER_HOVER};
}}
QPushButton:disabled {{
  color: #94a3b8;
  background: #f8fafc;
}}
"""

GLOBAL_BTN_BASE = (
    "QPushButton#globalInputBtn {"
    " border: 1px solid; padding: 4px 10px;"
    " min-width: 52px; min-height: 28px; max-height: 28px;"
    " border-radius: 6px; font-weight: 500;"
)

GLOBAL_BTN_OFF = (
    GLOBAL_BTN_BASE
    + f" background: {CARD_BG}; border-color: {INPUT_BORDER}; color: {TEXT_LABEL}; }}"
    "QPushButton#globalInputBtn:hover:!checked {"
    f" background-color: {HOVER_BTN_BG}; border: 1px solid {BORDER_HOVER}; }}"
)

GLOBAL_BTN_ON = (
    GLOBAL_BTN_BASE
    + " background-color: #dbeafe; border-color: #93c5fd;"
    f" color: {PRIMARY_DARK}; font-weight: 600; }}"
    "QPushButton#globalInputBtn:hover:checked {"
    f" background-color: #cfe2ff; border: 1px solid {BORDER_HOVER}; }}"
)

GLOBAL_BTN_UNSUPPORTED = (
    GLOBAL_BTN_BASE
    + f" border-color: #c8c8c8; background: #f3f4f6; color: #94a3b8; }}"
)

STATUS_LABEL_STYLE = "color: #555555; padding-left: 8px; padding-bottom: 4px;"
STATUS_MUTED_STYLE = STATUS_LABEL_STYLE
STATUS_ERROR_STYLE = f"color: {ERROR}; padding-left: 8px; padding-bottom: 4px;"


def main_window_stylesheet() -> str:
    return "\n".join(
        (
            APP_BACKGROUND_STYLE,
            CARD_STYLE,
            _settings_combo_style(),
            _combo_style(),
            INPUT_STYLE,
            OUTPUT_FIELD_STYLE,
            SEGMENTED_STYLE,
            SECONDARY_BTN_STYLE,
        )
    )


def make_section_card(
    object_name: str,
    *,
    margins: tuple[int, int, int, int] = (16, 16, 16, 16),
    spacing: int = 12,
) -> tuple[QWidget, QVBoxLayout]:
    card = QWidget()
    card.setObjectName(object_name)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return card, layout


def make_compact_section_card(object_name: str) -> tuple[QWidget, QVBoxLayout]:
    return make_section_card(
        object_name,
        margins=COMPACT_SECTION_MARGINS,
        spacing=COMPACT_SECTION_SPACING,
    )


def sync_compact_form_label_width(labels: list[QLabel]) -> None:
    """Size the label column to the widest caption so fields align on one column."""
    if not labels:
        return
    metrics = QFontMetrics(labels[0].font())
    width = max(
        SETTINGS_FORM_LABEL_MIN_WIDTH,
        max(metrics.horizontalAdvance(label.text()) for label in labels),
    )
    for label in labels:
        label.setWordWrap(False)
        label.setFixedWidth(width)


def align_settings_form_labels(labels: list[QLabel]) -> None:
    sync_compact_form_label_width(labels)


def compact_form_row(label: QLabel, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(COMPACT_ROW_SPACING)
    label.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(label)
    row.addWidget(widget, stretch=1)
    return row


def apply_compact_form_label_style(label: QLabel) -> None:
    label.setStyleSheet(COMPACT_FORM_LABEL_STYLE)


def apply_section_title_style(label: QLabel) -> None:
    label.setStyleSheet(SECTION_TITLE_STYLE)


def apply_combo_style(combo: QComboBox) -> None:
    combo.setStyleSheet(_combo_style())


def apply_secondary_btn_style(button: QWidget) -> None:
    button.setStyleSheet(SECONDARY_BTN_STYLE)
