from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from quicklingo import settings
from quicklingo.db import history
from quicklingo.features import is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.review_queue import count_due_today_all_decks
from quicklingo.ui.window_state import restore_window_geometry, save_window_geometry


class DashboardWindow(QDialog):
    _TOP_MODELS = 8

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        restore_window_geometry(self, "dashboard", default_width=920, default_height=620)
        layout = QVBoxLayout(self)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        charts = QHBoxLayout()
        self._daily_chart_view = QChartView()
        self._daily_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._model_chart_view = QChartView()
        self._model_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        charts.addWidget(self._daily_chart_view, stretch=1)
        charts.addWidget(self._model_chart_view, stretch=1)
        layout.addLayout(charts, stretch=1)

        self.retranslate_ui()
        self.refresh()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dashboard.title"))
        self.refresh()

    def refresh(self) -> None:
        self._update_summary()
        self._daily_chart_view.setVisible(is_enabled("history.dashboard"))
        self._model_chart_view.setVisible(is_enabled("history.model_stats"))
        if is_enabled("history.dashboard"):
            self._build_daily_chart()
        else:
            self._daily_chart_view.setChart(QChart())
        if is_enabled("history.model_stats"):
            self._build_model_chart()
        else:
            self._model_chart_view.setChart(QChart())

    def _update_summary(self) -> None:
        stats = history.get_translation_stats()
        parts = [tr("dashboard.total", count=stats.get("total", 0))]
        for key, label_key in (("ua-en", "dashboard.direction_ua_en"), ("en-ua", "dashboard.direction_en_ua")):
            if stats.get(key, 0):
                parts.append(tr(label_key, count=stats[key]))
        if is_enabled("learning.streak"):
            streak, _last = settings.get_learning_streak()
            parts.append(tr("dashboard.streak", streak=streak))
        if is_enabled("learning.daily_review"):
            due = count_due_today_all_decks()
            if due:
                parts.append(tr("dashboard.due_cards", count=due))
        self._summary_label.setText("  ·  ".join(parts))

    def _build_daily_chart(self) -> None:
        data = history.get_daily_counts(30)
        bar_set = QBarSet(tr("dashboard.translations"))
        categories: list[str] = []
        for day, count in data:
            bar_set.append(count)
            categories.append(day[5:10] if len(day) >= 10 else day)

        series = QBarSeries()
        series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(tr("dashboard.daily_activity"))
        chart.legend().setVisible(False)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        max_count = max((count for _day, count in data), default=0)
        axis_y.setRange(0, max(1, max_count))
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        self._daily_chart_view.setChart(chart)

    def _build_model_chart(self) -> None:
        rows = history.get_model_counts()
        chart = QChart()
        chart.setTitle(tr("dashboard.model_usage"))
        if not rows:
            self._model_chart_view.setChart(chart)
            return

        top = rows[: self._TOP_MODELS]
        other = sum(count for _model, count in rows[self._TOP_MODELS :])
        series = QPieSeries()
        for model, count in top:
            slice_ = series.append(model, count)
            slice_.setLabelVisible(count > 0)
        if other > 0:
            other_slice = series.append(tr("dashboard.other_models"), other)
            other_slice.setLabelVisible(True)

        chart.addSeries(series)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._model_chart_view.setChart(chart)

    def closeEvent(self, event: QCloseEvent) -> None:
        save_window_geometry(self, "dashboard")
        super().closeEvent(event)
