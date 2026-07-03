from __future__ import annotations

from dataclasses import dataclass

from quicklingo.db.learning import QuizCoverageStats


@dataclass(frozen=True)
class QuizGenerationOutcome:
    stats: QuizCoverageStats
    cancelled: bool = False
    failed_questions: int = 0
