# Quiz distractor hidden deck — mobile/web implementation prompt

Copy this prompt into a chat working on `d:\Develop\quicklingomobile` after desktop parity is merged.

---

**Task: Quiz distractor hidden deck (parity with desktop QuickLingo)**

**Context:** React Native + Expo, expo-router. Learning mirrors desktop: `src/db/learningRepository.ts`, `src/db/quizRepository.ts`, `src/learning/quiz/*`, UI `app/(tabs)/learning/quiz.tsx`, `QuizGenerationPanel.tsx`.

**Goal:** Store full AI-generated cards for english words that appear as quiz choice distractors (`quiz_questions.choices_pool`), in a global hidden deck per direction, so future quiz UI can show ukrainian/definition hints for wrong answers.

**Requirements:**

1. **Constants** — `QUIZ_DISTRACTOR_DECK_TAG = "__quiz-distractors"`, `QUIZ_DISTRACTOR_CARD_TYPE = "quiz_distractor"`, `QUIZ_DISTRACTOR_DECK_SOURCE = "quiz_distractor"`.

2. **Helpers** — `isQuizDistractorDeck(deck)`, `isQuizDistractorCard(card, deck?)`, `filterUserDecks(decks)`, `collectEnglishKeysAcrossDecks(direction)`.

3. **Global hidden deck** — one per direction (`ua-en`, `en-ua`): tag `__quiz-distractors`, `source: "quiz_distractor"`. One card per english covers distractors in **all** decks with that direction.

4. **Hide from UI** — deck pickers: cards, review, stats, quiz eligible decks, quiz-questions browser, create-deck tags. Exclude from due counts, deck summaries, analytics KPI scope, `listQuizEnglishWords` AI pool.

5. **Quiz tab button** — in `QuizGenerationPanel`: «Generate distractor cards ({count})». For resolved deck from quiz scope:
   - Collect unique english from `choices_pool` of active `quiz_questions` for that deck.
   - Subtract english already present on **any** card in **any** deck (same direction), including distractor deck.
   - If empty → show «all choice words already have cards».
   - Else run AI worker: same card batch pipeline as `aiDeckService` / desktop (`CARD_BATCH_SYSTEM_PROMPT`, `enrichCardFields`, batch upsert).
   - Target: `getOrCreateDistractorDeck(direction)`; upsert with `card_type: "quiz_distractor"`, `next_review_date` far future (not due for SRS).

6. **Lookup** — `lookupEnglishMetadata(english, direction)`: search user decks first, then distractor deck → `{ ukrainian, definition, examples, cardId, fromDistractorDeck }`. Foundation for future quiz wrong-answer UI (not required to ship full feedback in this task).

7. **Sync** — distractor deck and cards sync normally (`tag|direction`, card `sync_id`). No merge special-cases.

8. **Future-proof** — normal `learning_cards` rows (`deck_id` can be changed later for «promote to permanent deck» — not in this task).

9. **i18n** — en/uk: deck name, button, hint, progress, done, none messages.

**Desktop reference (after desktop implementation):**

- `quicklingo/learning/quiz/distractor_deck.py`
- `quicklingo/learning/quiz/distractor_words.py`
- `quicklingo/learning/quiz/choice_lookup.py`
- `quicklingo/workers/ai_distractor_cards_worker.py`
- `quicklingo/ui/widgets/quiz_generation_panel.py`
- Filters: `learning_window`, `aggregator`, `learning_due`, `learning_reviews`, `learning_progress`, `quiz_questions_browser`, `learning/analytics/repository`

**Web:** Cloudflare worker merge (`worker/merge.ts`) should need no changes if deck/card rows are standard.

---
