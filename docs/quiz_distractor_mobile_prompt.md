# Колода дистракторів квізу — промпт для quicklingomobile

Скопіюй цей текст у чат для `d:\Develop\quicklingomobile`, коли desktop QuickLingo уже змерджено.

---

## Задача: паритет з desktop QuickLingo (фінальна версія)

**Контекст:** React Native + Expo, expo-router. Learning повторює desktop: `src/db/learningRepository.ts`, `src/db/quizRepository.ts`, `src/learning/quiz/*`, UI `app/(tabs)/learning/quiz.tsx`, `QuizGenerationPanel.tsx`.

**Ціль:** Зберігати **повні AI-картки** для english-слів з `quiz_questions.choices_pool` у **глобальній прихованій колоді** (одна на напрямок). Ці картки використовуються в **квізі** — після неправильного вибору показувати переклад / definition обраного english-варіанта (дистрактор або слово з основної колоди).

---

## 1. Константи

- `QUIZ_DISTRACTOR_DECK_TAG = "__quiz-distractors"`
- `QUIZ_DISTRACTOR_CARD_TYPE = "quiz_distractor"`
- `QUIZ_DISTRACTOR_DECK_SOURCE = "quiz_distractor"`
- `NO_REVIEW_SCHEDULE_DATE = "2099-12-31"` — картки дистракторів **не в SRS / не due**

---

## 2. Нормалізація english для матчінгу

`normalizeEnglishQuizKey(text)` (`quicklingo/learning/quiz/normalize.py`):

- trim + lowercase (`collapseWhitespace`)
- зрізати статті на початку: `the `, `a `, `an `

Використовується в:

- `collectMissingDistractorWords` — «вже покрито» карткою
- `collectEnglishKeysAcrossDecks`
- `lookupEnglishMetadata` — `the problem` знаходить картку `problem`
- upsert дистракторів по english key

---

## 3. Helpers (`distractor_deck`)

- `isQuizDistractorDeck(deck)` — `deck.tag === "__quiz-distractors"`
- `isQuizDistractorCard(card, deck?)` — `card_type === quiz_distractor` або картка в distractor deck
- `filterUserDecks(decks)` — без distractor deck
- `collectEnglishKeysAcrossDecks(direction, includeDistractorDeck?)` — множина normalized english keys з усіх колод напрямку

---

## 4. Глобальна прихована колода

- Одна на напрямок (`ua-en`, `en-ua`): tag `__quiz-distractors`, `source: quiz_distractor`
- `getOrCreateDistractorDeck(direction)` — display name з i18n `learning.quiz_distractor_deck_name`
- **Одна картка на english** покриває дистрактори в **усіх** колодах цього напрямку
- Картки: `card_type: quiz_distractor`, `next_review_date: 2099-12-31`

---

## 5. Сховати distractor deck з UI

Не показувати в:

- пікери колод: картки, повторення, статистика, quiz eligible decks, quiz-questions browser, create-deck tags
- due counts, deck summaries, analytics KPI
- `listQuizEnglishWords` (AI pool для нових quiz distractors)

Файли desktop з фільтрами: `learning_window`, `aggregator`, `learning_due`, `learning_reviews`, `learning_progress`, `quiz_questions_browser`, `learning/analytics/repository`.

---

## 6. Генерація карток (Quiz tab)

**UI:** `QuizGenerationPanel` — одна кнопка **«Згенерувати картки дистракторів ({count})»** (без авто-циклу).

**Логіка missing** (`distractor_words.collectMissingDistractorWords(deckId)`):

1. Унікальні english з `choices_pool` active `quiz_questions` **цієї колоди**
2. Відняти english, що вже є на **будь-якій** картці **будь-якої** колоди (той напрямок), включно з distractor deck — через `normalizeEnglishQuizKey`
3. Якщо порожньо → hint «всі слова вже з картками»

**Worker** (`AiDistractorCardsWorker`): один прохід на весь список missing; `batch_size` з feature `learning.quiz.distractor_batch_size` (default **5**); налаштування в Settings → Learning limits.

**Сервіс** (`AiDistractorService`):

- Той самий pipeline що AI deck: `CARD_BATCH_SYSTEM_PROMPT`, `buildAiWordCardPrompt`, `parseAnalysisResponse`, `enrichCardFields`
- Target: `getOrCreateDistractorDeck(direction)` → `batchUpsertCards`
- При **429 / rate limit**: **ділити batch навпіл** і пробувати знову (не нескінченний retry того самого великого batch)
- При зламаному JSON: split навпіл (як rate limit)
- Ручний режим: при rate limit на **одне слово** — **стоп**, показати `rate_limited` + `retry_seconds`, кнопка знову доступна
- **Матчінг відповіді AI до слова з quiz:**
  - по normalized english term
  - fallback по **індексу** в batch (synonym: AI `benefit` → quiz word `advantage`)
  - **примусово** записати english з quiz pool у картку (`back` для ua-en, `front` для en-ua) — не «the problem», а `problem` з `choices_pool`
- Прогрес: `words_done/total (batch i/n)`; при пустому match / пустій відповіді — i18n batch_no_match / empty_response / parse_failed

---

## 7. Upsert в БД (`batch_upsert_cards`)

Для `card_type === quiz_distractor`:

- **Не** матчити по `front` (українська) — **індекс по normalized english key** на стороні english (`back` для ua-en)
- Дві картки з одним `front` але різним english (`the problem` / `issue`) — **дві рядки**, не overwrite
- Оновлення `content_updated_at` при зміні контенту

---

## 8. Lookup і фідбек у квізі (**обов’язково в mobile**)

`lookupEnglishMetadata(english, direction)` (`choice_lookup.py`):

1. Спочатку **user decks** (не distractor)
2. Потім distractor deck по tag + direction
3. Матч по `normalizeEnglishQuizKey`
4. Return: `{ english, ukrainian, definition, examples, cardId, fromDistractorDeck }`

`formatWrongChoiceFeedback(english, direction)`:

- Є ukrainian → `Твій вибір «{english}» — {ukrainian}`
- Лише definition → `Твій вибір «{english}»: {definition}`
- Немає картки → `Картки для «{english}» не знайдено.`

**Quiz session UI** (`quiz_session.py`):

- Для **всіх трьох типів** (translation recall, fill blank, definition match) — варіанти на кнопках **english**
- Після **неправильного** кліку: текст під варіантами через `formatWrongChoiceFeedback`
- **Зарезервований слот** фіксованої висоти (~48px) під підказку — **без скачку layout** (питання і кнопки не зміщуються)
- На екрані результатів: у колонці «Твій вибір» теж текст з перекладом (той самий helper)

i18n: `learning.quiz_wrong_choice_hint`, `quiz_wrong_choice_definition`, `quiz_wrong_choice_unknown`.

---

## 9. Sync

Distractor deck і картки синхронізуються **стандартно** (`history.db` snapshot):

- Deck identity: `tag + direction`
- Card identity: `sync_id`
- Без спеціальних merge-правил

Cloudflare worker `worker/merge.ts` — без змін, якщо рядки стандартні `learning_decks` / `learning_cards`.

---

## 10. i18n (en + uk)

Генерація:

- `learning.quiz_distractor_deck_name`
- `learning.quiz_distractor_cards_btn`, `hint`, `progress_batch`, `generating`, `done`, `none`, `cancelled`, `partial`, `rate_limit_paused`, `batch_no_match`, `batch_empty_response`, `batch_parse_failed`

Settings:

- `settings.features.quiz_distractor_batch_size`

Квіз фідбек:

- `learning.quiz_wrong_choice_hint`, `quiz_wrong_choice_definition`, `quiz_wrong_choice_unknown`

---

## 11. Що **ще не** в desktop (не блокує mobile parity)

- Пункт меню «Колоди дистракторів» / груповий перенос у основні колоди зі зміною тега — **заплановано**, не реалізовано
- Авто-цикл генерації — **видалено** (лише ручна кнопка + повторний клік)

---

## 12. Desktop reference (актуальні файли)

| Файл | Роль |
|------|------|
| `quicklingo/learning/quiz/distractor_deck.py` | константи, filters, collect keys |
| `quicklingo/learning/quiz/distractor_words.py` | missing words |
| `quicklingo/learning/quiz/normalize.py` | `normalize_english_quiz_key` |
| `quicklingo/learning/quiz/choice_lookup.py` | lookup + `format_wrong_choice_feedback` |
| `quicklingo/learning/quiz/ai_distractor_service.py` | AI batch generation |
| `quicklingo/workers/ai_distractor_cards_worker.py` | QThread worker |
| `quicklingo/db/learning_cards.py` | upsert по english key для distractor |
| `quicklingo/ui/widgets/quiz_generation_panel.py` | кнопка генерації |
| `quicklingo/ui/widgets/quiz_session.py` | фідбек wrong choice + reserved slot |
| `tests/test_quiz_distractor_deck.py`, `tests/test_ai_distractor_service.py` | тести |

---

## 13. Критерії готовності mobile

- [ ] Hidden deck + генерація + batch upsert по english key
- [ ] Missing count з нормалізацією статей
- [ ] Sync distractor deck/cards
- [ ] Lookup + підказка під варіантами для всіх типів квізу
- [ ] Фіксований слот під підказку (без layout jump)
- [ ] Фільтри UI (distractor deck не в списках колод)

---
