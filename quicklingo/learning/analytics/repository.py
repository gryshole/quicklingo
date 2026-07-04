from __future__ import annotations

from datetime import date, timedelta

from quicklingo.db.connection import connection
from quicklingo.db.learning import LearningCard, list_cards, list_decks
from quicklingo.learning.analytics.mastered import is_learning, is_mastered
from quicklingo.learning.analytics.models import (
    DailyActivityDto,
    LearningDashboardDto,
    LearningKpiDto,
    MasteredTrendPointDto,
)


class LearningAnalyticsRepository:
    def refresh(self, deck_id: int | None = None) -> LearningDashboardDto:
        with connection() as conn:
            kpi = self._load_kpi(conn, deck_id=deck_id)
            activity = self._load_activity(conn)
            trend = self._load_mastered_trend(deck_id=deck_id)
        return LearningDashboardDto(kpi=kpi, activity=activity, mastered_trend=trend)

    def _cards_for_scope(self, deck_id: int | None) -> list[LearningCard]:
        if deck_id is None:
            return self._all_cards()
        return list_cards(deck_id)

    def _load_kpi(self, conn, *, deck_id: int | None = None) -> LearningKpiDto:
        cards = self._cards_for_scope(deck_id)
        total = len(cards)
        learning_count = sum(1 for card in cards if is_learning(card))
        mastered_count = sum(1 for card in cards if is_mastered(card))

        card_ids = [card.id for card in cards]
        review_clause = ""
        quiz_clause = ""
        review_params: list[object] = []
        quiz_params: list[object] = []
        if card_ids:
            placeholders = ",".join("?" * len(card_ids))
            review_clause = f" AND card_id IN ({placeholders})"
            quiz_clause = f" AND card_id IN ({placeholders})"
            review_params = list(card_ids)
            quiz_params = list(card_ids)

        review_row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) AS correct
            FROM review_logs
            WHERE was_correct IS NOT NULL AND mode != 'cram'{review_clause}
            """,
            review_params,
        ).fetchone()
        review_total = int(review_row["total"] or 0)
        review_correct = int(review_row["correct"] or 0)

        quiz_row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END) AS correct
            FROM quiz_logs
            WHERE 1=1{quiz_clause}
            """,
            quiz_params,
        ).fetchone()
        quiz_total = int(quiz_row["total"] or 0)
        quiz_correct = int(quiz_row["correct"] or 0)

        combined_total = review_total + quiz_total
        combined_correct = review_correct + quiz_correct
        accuracy = None
        if combined_total > 0:
            accuracy = round(combined_correct * 100.0 / combined_total, 1)
        review_accuracy = None
        if review_total > 0:
            review_accuracy = round(review_correct * 100.0 / review_total, 1)
        quiz_accuracy = None
        if quiz_total > 0:
            quiz_accuracy = round(quiz_correct * 100.0 / quiz_total, 1)

        return LearningKpiDto(
            total_cards=total,
            learning_cards=learning_count,
            mastered_cards=mastered_count,
            accuracy_percent=accuracy,
            review_accuracy_percent=review_accuracy,
            quiz_accuracy_percent=quiz_accuracy,
            review_answer_count=review_total,
            quiz_answer_count=quiz_total,
        )

    def _load_activity(self, conn) -> list[DailyActivityDto]:
        rows = conn.execute(
            """
            SELECT day, SUM(cnt) AS cnt FROM (
                SELECT date(reviewed_at) AS day, COUNT(*) AS cnt
                FROM review_logs
                WHERE reviewed_at >= date('now', '-182 days') AND mode != 'cram'
                GROUP BY date(reviewed_at)
                UNION ALL
                SELECT date(answered_at) AS day, COUNT(*) AS cnt
                FROM quiz_logs
                WHERE answered_at >= date('now', '-182 days')
                GROUP BY date(answered_at)
            )
            GROUP BY day
            ORDER BY day
            """
        ).fetchall()
        return [
            DailyActivityDto(day=date.fromisoformat(row["day"]), count=int(row["cnt"]))
            for row in rows
            if row["day"]
        ]

    def _load_mastered_trend(self, *, deck_id: int | None = None) -> list[MasteredTrendPointDto]:
        cards = self._cards_for_scope(deck_id)
        today = date.today()
        points: list[MasteredTrendPointDto] = []
        for week_offset in range(11, -1, -1):
            week_end = today - timedelta(days=week_offset * 7)
            count = sum(
                1
                for card in cards
                if is_mastered(card)
                and (card.last_reviewed or "")[:10] <= week_end.isoformat()
            )
            label = week_end.strftime("%d.%m")
            points.append(
                MasteredTrendPointDto(
                    week_label=label,
                    week_end=week_end,
                    mastered_count=count,
                )
            )
        return points

    def _all_cards(self) -> list[LearningCard]:
        cards: list[LearningCard] = []
        for deck in list_decks():
            cards.extend(list_cards(deck.id))
        return cards
