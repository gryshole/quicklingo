"""Shared Quiz-style palette and QSS for the main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

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
ERROR = "#dc2626"
RADIUS_CARD = "12px"
RADIUS_CONTROL = "8px"

SETTINGS_LABEL_WIDTH = 108  # fallback until labels are measured
COMPACT_ROW_SPACING = 3
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
    f"color: {PLACEHOLDER_MUTED}; font-size: 9pt;"
    f" font-weight: 600; letter-spacing: 1.2px; margin-bottom: 8px;"
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


def apply_combo_font(combo: QComboBox) -> None:
    """Ensure combo, popup list, and line edit use a valid point-size font."""
    if getattr(combo, "_ql_combo_font_patched", False):
        return

    font = settings_ui_font(combo.font().family())
    combo.setFont(font)
    view = combo.view()
    if view is not None:
        view.setFont(font)
    line_edit = combo.lineEdit()
    if line_edit is not None:
        line_edit.setFont(font)

    original_show_popup = combo.showPopup

    def show_popup_with_font() -> None:
        ensure_valid_point_font(combo)
        popup_view = combo.view()
        if popup_view is not None:
            popup_view.setFont(settings_ui_font(combo.font().family()))
        original_show_popup()

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
QWidget#settingsCard QComboBox:focus, QWidget#settingsCard QComboBox:on {{
  border-color: {PRIMARY};
}}
QWidget#settingsCard QComboBox QAbstractItemView {{
  border: 1px solid {INPUT_BORDER};
  border-radius: 6px;
  background: {CARD_BG};
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
QComboBox QAbstractItemView {{
  border: 1px solid {INPUT_BORDER};
  border-radius: {RADIUS_CONTROL};
  background: {CARD_BG};
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
QTextEdit#mainInput:focus, QLineEdit#mainInput:focus {{
  border-color: {PRIMARY};
}}
"""

OUTPUT_PLACEHOLDER_STYLE = (
    f"color: {PLACEHOLDER_MUTED}; font-size: 10pt; background: transparent;"
)

SEGMENTED_STYLE = f"""
QWidget#segmentedControl {{
  background: #f1f5f9;
  border-radius: 6px;
}}
QWidget#settingsCard QWidget#segmentedControl {{
  max-height: {SETTINGS_CONTROL_HEIGHT}px;
}}
QWidget#segmentedControl QPushButton {{
  background: transparent;
  border: none;
  border-radius: 5px;
  padding: 2px 8px;
  color: {TEXT_MUTED};
  font-weight: 500;
  font-size: {SETTINGS_FONT_PT}pt;
  min-height: {SETTINGS_CONTROL_HEIGHT}px;
  max-height: {SETTINGS_CONTROL_HEIGHT}px;
}}
QWidget#segmentedControl QPushButton:checked {{
  background: #eff6ff;
  color: {PRIMARY_DARK};
  font-weight: 600;
}}
QWidget#segmentedControl QPushButton:hover:!checked {{
  background: #e2e8f0;
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
  background: #f1f5f9;
  border-color: #94a3b8;
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
    f" border-radius: {RADIUS_CONTROL}; font-weight: 500;"
)

GLOBAL_BTN_OFF = (
    GLOBAL_BTN_BASE
    + f" background: {CARD_BG}; border-color: {INPUT_BORDER}; color: {TEXT_LABEL}; }}"
)

GLOBAL_BTN_ON = (
    GLOBAL_BTN_BASE
    + " background-color: #dbeafe; border-color: #93c5fd;"
    f" color: {PRIMARY_DARK}; font-weight: 600; }}"
)

GLOBAL_BTN_UNSUPPORTED = (
    GLOBAL_BTN_BASE
    + f" border-color: #c8c8c8; background: #f3f4f6; color: #94a3b8; }}"
)

STATUS_MUTED_STYLE = f"color: {TEXT_MUTED};"
STATUS_ERROR_STYLE = f"color: {ERROR};"


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
    """Size the label column to the widest caption so fields sit close to the text."""
    if not labels:
        return
    metrics = QFontMetrics(labels[0].font())
    width = max(metrics.horizontalAdvance(label.text()) for label in labels)
    for label in labels:
        label.setWordWrap(False)
        label.setFixedWidth(width)


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
