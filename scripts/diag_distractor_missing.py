"""One-off diagnostic: missing distractor words per deck."""
from quicklingo.db import connection as c
from quicklingo.db.history_schema import init_db
from quicklingo.db.learning import list_quiz_questions
from quicklingo.learning.quiz.aggregator import list_quiz_eligible_decks
from quicklingo.learning.quiz.distractor_words import (
    collect_missing_distractor_words,
    count_missing_distractor_words_in_scope,
    resolve_distractor_generation_deck_id,
)

init_db()
print("db:", c.db_path())
for deck in list_quiz_eligible_decks():
    missing = collect_missing_distractor_words(deck.id)
    qcount = len(list_quiz_questions(deck.id, status="active"))
    print(
        f"deck {deck.id} {deck.name!r} tag={deck.tag} "
        f"active_q={qcount} missing={len(missing)} sample={missing[:8]}"
    )
print("resolved:", resolve_distractor_generation_deck_id(None))
print("scope total:", count_missing_distractor_words_in_scope(None))
