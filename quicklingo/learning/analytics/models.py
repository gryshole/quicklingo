from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class LearningKpiDto:
    total_cards: int = 0
    learning_cards: int = 0
    mastered_cards: int = 0
    accuracy_percent: float | None = None
    review_accuracy_percent: float | None = None
    quiz_accuracy_percent: float | None = None
    review_answer_count: int = 0
    quiz_answer_count: int = 0


@dataclass
class DailyActivityDto:
    day: date
    count: int


@dataclass
class MasteredTrendPointDto:
    week_label: str
    week_end: date
    mastered_count: int


@dataclass
class LearningDashboardDto:
    kpi: LearningKpiDto = field(default_factory=LearningKpiDto)
    activity: list[DailyActivityDto] = field(default_factory=list)
    mastered_trend: list[MasteredTrendPointDto] = field(default_factory=list)
