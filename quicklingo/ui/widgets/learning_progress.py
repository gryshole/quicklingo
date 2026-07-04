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

_KPI_STYLE = """
    QWidget#kpiCard {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
    }
"""


class _KpiCard(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("kpiCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        self._value = QLabel("0")
        value_font = QFont()
        value_font.setPointSize(16)
        value_font.setBold(True)
        self._value.setFont(value_font)
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: #64748b; font-size: 9pt;")
        layout.addWidget(self._value)
        layout.addWidget(self._label)

    def set_data(self, value: str, label: str, *, tooltip: str = "") -> None:
        self._value.setText(value)
        self._label.setText(label)
        if tooltip:
            self.setToolTip(tooltip)
        else:
            self.setToolTip("")


class LearningProgressWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_KPI_STYLE)
        self._repo = LearningAnalyticsRepository()
        self._deck_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        deck_row = QHBoxLayout()
        self._deck_filter_label = QLabel()
        self._deck_filter = QComboBox()
        self._deck_filter.currentIndexChanged.connect(self._on_deck_filter_changed)
        deck_row.addWidget(self._deck_filter_label)
        deck_row.addWidget(self._deck_filter, stretch=1)
        root.addLayout(deck_row)

        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet("color: #64748b; font-size: 11pt; padding: 24px;")
        self._empty_label.setVisible(False)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
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
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            kpi_row.addWidget(card, stretch=1)
        content_layout.addLayout(kpi_row)

        self._heatmap_title = QLabel()
        self._heatmap_title.setStyleSheet("font-weight: 600; color: #334155; font-size: 10pt;")
        self._heatmap = ActivityHeatmapWidget()
        content_layout.addWidget(self._heatmap_title)
        content_layout.addWidget(self._heatmap)

        self._chart_title = QLabel()
        self._chart_title.setStyleSheet("font-weight: 600; color: #334155; font-size: 10pt;")
        self._chart_view = QChartView()
        self._chart_view.setMinimumHeight(140)
        self._chart_view.setMaximumHeight(180)
        self._chart_view.setRenderHint(self._chart_view.renderHints())
        content_layout.addWidget(self._chart_title)
        content_layout.addWidget(self._chart_view)
        content_layout.addStretch(1)

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
        chart.setMargins(QMargins(0, 0, 0, 0))
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
        axis_y = QValueAxis()
        max_y = max(point.mastered_count for point in points)
        axis_y.setRange(0, max(1, max_y))
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        self._chart_view.setChart(chart)
