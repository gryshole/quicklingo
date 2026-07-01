from __future__ import annotations

from quicklingo.db import learning
from quicklingo.learning.review_queue import SessionQueue


def build_cram_queue(cards: list[learning.LearningCard]) -> SessionQueue:
    return SessionQueue(cards=list(cards))


def cram_hard_cards(deck_id: int) -> list[learning.LearningCard]:
    return learning.list_struggled_cards_today(deck_id)


def cram_train_cards(
    deck_id: int,
    session_card_ids: list[int],
) -> list[learning.LearningCard]:
    struggled = learning.list_struggled_cards_today(deck_id)
    if struggled:
        return struggled
    reviewed = learning.list_reviewed_cards_today(deck_id)
    if reviewed:
        return reviewed
    if session_card_ids:
        order = {card_id: index for index, card_id in enumerate(session_card_ids)}
        cards = learning.list_cards_by_ids(session_card_ids)
        cards.sort(key=lambda card: order.get(card.id, len(session_card_ids)))
        return cards
    return learning.list_cards(deck_id)
