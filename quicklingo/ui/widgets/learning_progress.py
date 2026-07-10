from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_direction_label
from quicklingo.db import learning
from quicklingo.i18n import tr
from quicklingo.learning.analytics.repository import LearningAnalyticsRepository
from quicklingo.ui.widgets.activity_heatmap import ActivityHeatmapWidget

_PAGE_MARGIN = 16
_SECTION_GAP = 20
_TITLE_TO_BODY_GAP = 12

_PROGRESS_STYLE = """
LearningProgressWidget {
    background: transparent;
}
QLabel#deckFilterLabel {
    color: #334155;
    font-size: 12px;
    margin: 0px;
    padding: 0px;
}
QComboBox#progressDeckFilter {
    max-width: 300px;
    margin: 0px;
}
QWidget#kpiStrip {
    background: transparent;
    margin: 0px;
    padding: 0px;
}
QWidget#kpiCard,
QFrame#statsCard {
    background-color: white;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
}
QLabel#kpiValue {
    color: #1e293b;
    font-size: 18pt;
    font-weight: 700;
}
QLabel#kpiLabel {
    color: #64748b;
    font-size: 9pt;
}
QLabel#sectionTitle {
    color: #1e293b;
    font-size: 15px;
    font-weight: 600;
    margin: 0px;
    padding: 0px;
}
QChartView#progressTrendChart {
    background: transparent;
    border: none;
}
"""


class _KpiCard(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(4)
        self._value = QLabel("0")
        self._value.setObjectName("kpiValue")
        value_font = QFont()
        value_font.setPointSize(16)
        value_font.setBold(True)
        self._value.setFont(value_font)
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label = QLabel()
        self._label.setObjectName("kpiLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._value)
        layout.addWidget(self._label)

    def set_data(self, value: str, label: str, *, tooltip: str = "") -> None:
        self._value.setText(value)
        self._label.setText(label)
        self.setToolTip(tooltip or "")


def _integer_y_axis(max_value: int) -> QValueAxis:
    max_y = max(1, int(max_value))
    axis = QValueAxis()
    axis.setLabelFormat("%d")
    axis.setMinorTickCount(0)
    if max_y <= 5:
        axis.setRange(0, max_y)
        axis.setTickCount(max_y + 1)
        return axis

    step = max(1, (max_y + 4) // 5)
    nice_max = ((max_y + step - 1) // step) * step
    axis.setRange(0, nice_max)
    axis.setTickCount(nice_max // step + 1)
    return axis


def _make_stats_card() -> QFrame:
    card = QFrame()
    card.setObjectName("statsCard")
    card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    card.setMinimumWidth(0)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return card


def _full_width_row() -> QWidget:
    row = QWidget()
    row.setObjectName("kpiStrip")
    row.setMinimumWidth(0)
    row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return row


class LearningProgressWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LearningProgressWidget")
        self.setStyleSheet(_PROGRESS_STYLE)
        self._repo = LearningAnalyticsRepository()
        self._deck_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet("color: #64748b; font-size: 11pt; padding: 24px;")
        self._empty_label.setVisible(False)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Single column: every block stretches to the same left/right edges.
        content = QWidget()
        content.setMinimumWidth(0)
        column = QVBoxLayout(content)
        column.setContentsMargins(_PAGE_MARGIN, _PAGE_MARGIN, _PAGE_MARGIN, _PAGE_MARGIN)
        column.setSpacing(_SECTION_GAP)
        column.setAlignment(Qt.AlignmentFlag.AlignTop)

        deck_row = QHBoxLayout()
        deck_row.setContentsMargins(0, 0, 0, 0)
        deck_row.setSpacing(8)
        self._deck_filter_label = QLabel()
        self._deck_filter_label.setObjectName("deckFilterLabel")
        self._deck_filter_label.setIndent(0)
        self._deck_filter_label.setMargin(0)
        self._deck_filter_label.setContentsMargins(0, 0, 0, 0)
        self._deck_filter = QComboBox()
        self._deck_filter.setObjectName("progressDeckFilter")
        self._deck_filter.setMaximumWidth(300)
        self._deck_filter.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._deck_filter.currentIndexChanged.connect(self._on_deck_filter_changed)
        deck_row.addWidget(self._deck_filter_label, 0, Qt.AlignmentFlag.AlignLeft)
        deck_row.addWidget(self._deck_filter, 0, Qt.AlignmentFlag.AlignLeft)
        deck_row.addStretch(1)
        column.addLayout(deck_row)

        kpi_strip = _full_width_row()
        kpi_row = QHBoxLayout(kpi_strip)
        kpi_row.setContentsMargins(0, 0, 0, 0)
        kpi_row.setSpacing(12)
        self._kpi_total = _KpiCard()
        self._kpi_learning = _KpiCard()
        self._kpi_mastered = _KpiCard()
        self._kpi_accuracy = _KpiCard()
        for card in (
            self._kpi_total,
            self._kpi_learning,
            self._kpi_mastered,
            self._kpi_accuracy,
        ):
            kpi_row.addWidget(card, stretch=1)
        column.addWidget(kpi_strip)

        # Titles sit OUTSIDE cards so their left edge matches the card outer border.
        self._heatmap_title = QLabel()
        self._heatmap_title.setObjectName("sectionTitle")
        self._heatmap_title.setIndent(0)
        self._heatmap_title.setMargin(0)
        self._heatmap_title.setContentsMargins(0, 0, 0, 0)
        self._heatmap = ActivityHeatmapWidget()
        self._heatmap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        heatmap_card = _make_stats_card()
        heatmap_layout = QVBoxLayout(heatmap_card)
        heatmap_layout.setContentsMargins(20, 20, 20, 20)
        heatmap_layout.setSpacing(0)
        heatmap_center = QHBoxLayout()
        heatmap_center.setContentsMargins(0, 0, 0, 0)
        heatmap_center.addStretch(1)
        heatmap_center.addWidget(self._heatmap, 0, Qt.AlignmentFlag.AlignCenter)
        heatmap_center.addStretch(1)
        heatmap_layout.addLayout(heatmap_center)
        heatmap_section = QVBoxLayout()
        heatmap_section.setContentsMargins(0, 0, 0, 0)
        heatmap_section.setSpacing(_TITLE_TO_BODY_GAP)
        heatmap_section.addWidget(self._heatmap_title)
        heatmap_section.addWidget(heatmap_card)
        column.addLayout(heatmap_section)

        self._chart_title = QLabel()
        self._chart_title.setObjectName("sectionTitle")
        self._chart_title.setIndent(0)
        self._chart_title.setMargin(0)
        self._chart_title.setContentsMargins(0, 0, 0, 0)
        chart_card = _make_stats_card()
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(12, 12, 12, 12)
        chart_layout.setSpacing(0)
        self._chart_view = QChartView()
        self._chart_view.setObjectName("progressTrendChart")
        self._chart_view.setMinimumHeight(160)
        self._chart_view.setMaximumHeight(200)
        self._chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._chart_view.setRenderHint(self._chart_view.renderHints())
        chart_layout.addWidget(self._chart_view)
        chart_section = QVBoxLayout()
        chart_section.setContentsMargins(0, 0, 0, 0)
        chart_section.setSpacing(_TITLE_TO_BODY_GAP)
        chart_section.addWidget(self._chart_title)
        chart_section.addWidget(chart_card)
        column.addLayout(chart_section)

        column.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)
        root.addWidget(self._empty_label)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._deck_filter_label.setText(tr("learning.progress_deck_filter"))
        self._reload_deck_filter()
        self._heatmap_title.setText(tr("learning.progress_activity"))
        self._chart_title.setText(tr("learning.progress_mastered_trend"))
        self.refresh()

    def _reload_deck_filter(self) -> None:
        current = self._deck_filter.currentData()
        self._deck_filter.blockSignals(True)
        self._deck_filter.clear()
        self._deck_filter.addItem(tr("learning.progress_all_decks"), None)
        for deck in learning.list_decks():
            label = f"{deck.name} ({get_direction_label(deck.direction)})"
            self._deck_filter.addItem(label, deck.id)
        if current is not None:
            index = self._deck_filter.findData(current)
            if index >= 0:
                self._deck_filter.setCurrentIndex(index)
        self._deck_filter.blockSignals(False)

    def _on_deck_filter_changed(self) -> None:
        data = self._deck_filter.currentData()
        self._deck_id = int(data) if data is not None else None
        self.refresh()

    def refresh(self) -> None:
        self._empty_label.setVisible(False)
        dashboard = self._repo.refresh(deck_id=self._deck_id)
        kpi = dashboard.kpi
        self._kpi_total.set_data(str(kpi.total_cards), tr("learning.progress_kpi_total"))
        self._kpi_learning.set_data(str(kpi.learning_cards), tr("learning.progress_kpi_learning"))
        self._kpi_mastered.set_data(str(kpi.mastered_cards), tr("learning.progress_kpi_mastered"))
        accuracy_text = "—"
        accuracy_tooltip = ""
        if kpi.accuracy_percent is not None:
            accuracy_text = f"{kpi.accuracy_percent:.0f}%"
            if kpi.quiz_answer_count == 0:
                accuracy_tooltip = tr("learning.progress_accuracy_reviews_only")
            else:
                accuracy_tooltip = tr(
                    "learning.progress_accuracy_split",
                    review=kpi.review_accuracy_percent or 0,
                    quiz=kpi.quiz_accuracy_percent or 0,
                )
        self._kpi_accuracy.set_data(
            accuracy_text,
            tr("learning.progress_kpi_accuracy"),
            tooltip=accuracy_tooltip,
        )
        self._heatmap.set_activity(dashboard.activity)
        self._build_trend_chart(dashboard.mastered_trend)
        if kpi.total_cards == 0:
            self._empty_label.setText(tr("learning.progress_no_cards"))
            self._empty_label.setVisible(True)

    def _build_trend_chart(self, points) -> None:
        chart = QChart()
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(8, 8, 8, 8))
        chart.setBackgroundVisible(False)
        if not points:
            self._chart_view.setChart(chart)
            return
        series = QLineSeries()
        for index, point in enumerate(points):
            series.append(index, point.mastered_count)
        chart.addSeries(series)
        axis_x = QValueAxis()
        axis_x.setRange(0, max(1, len(points) - 1))
        axis_x.setLabelsVisible(False)
        axis_x.setMinorTickCount(0)
        max_y = max(point.mastered_count for point in points)
        axis_y = _integer_y_axis(max_y)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        self._chart_view.setChart(chart)
