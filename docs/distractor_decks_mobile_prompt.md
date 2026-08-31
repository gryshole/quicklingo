# Колоди дистракторів — промпт для quicklingomobile

Скопіюй цей текст у чат для `d:\Develop\quicklingomobile`, коли desktop QuickLingo уже змерджено і distractor deck з [`docs/quiz_distractor_mobile_prompt.md`](quiz_distractor_mobile_prompt.md) реалізовано (або паралельно, якщо базова колода дистракторів уже є).

---

## Задача: паритет з desktop — браузер дистракторів + перенос у основні колоди

**Контекст:** React Native + Expo, expo-router. Learning повторює desktop: `src/db/learningRepository.ts`, quiz distractor helpers з першого prompt.

**Ціль:** Додати **UI для перегляду** карток у прихованих колодах дистракторів (`__quiz-distractors`) і **груповий перенос** у основні колоди з вибором **тега** (і опційно назви колоди). Це **не** повторення AI-генерації дистракторів — лише браузер + transfer.

**Desktop reference:** `quicklingo/ui/distractor_decks_window.py`, `quicklingo/ui/widgets/distractor_cards_browser.py`, `quicklingo/ui/dialogs/distractor_transfer_dialog.py`, `quicklingo/learning/quiz/distractor_transfer.py`.

---

## 1. Пункт меню / навігація

- Аналог desktop: **Інструменти → Колоди дистракторів** (`main.menu_distractor_decks`).
- В mobile: entry в tools/settings або learning admin (де вже «Питання квізу» / quiz tools).
- Видимий при увімкненій функції `learning.quiz`.

---

## 2. Екран браузера

**Фільтр колоди / напрямку**

- Combo лише з `isQuizDistractorDeck(deck)` — одна колода на напрямок (`ua-en`, `en-ua`).
- Label: `{deck.name} ({direction label})`.

**Пошук**

- Поле пошуку: front, back, hint, notes (case-insensitive substring).

**Таблиця / список**

- Колонки: Front, Back, Hint, Notes, Next review (для дистракторів зазвичай `2099-12-31`).
- **Мультивибір** рядків (checkbox або long-press + select).
- Бейдж: `{count} cards` (`learning.distractor_decks_count`).

**Дії**

- Refresh
- Edit (один рядок) — ті самі поля що картка навчання
- Delete (один або виділені)
- **«Перенести в колоду…»** (`learning.distractor_decks_transfer_btn`) — відкриває діалог переносу

Подвійний тап / tap — edit.

---

## 3. Діалог переносу

**Поля**

- **Тег колоди** (`learning.distractor_decks_target_tag`) — editable combo:
  - теги з history (`getTagCounts(direction, learningKind: true)`);
  - теги user decks (`filterUserDecks`) для того напрямку;
  - можливість ввести новий тег.
- **Назва колоди** (`learning.distractor_decks_target_name`) — опційно; default = тег.

**Підказка** (`learning.distractor_decks_transfer_hint`):

> Перенести N виділених карток у основну колоду. Якщо картка з таким front уже є — порожні поля доповнюються, картка дистрактора **видаляється**.

**Scope:** лише **виділені** картки. Якщо нічого не виділено — `learning.distractor_decks_transfer_none_selected`.

**Результат** (`learning.distractor_decks_transfer_done`):

> Перенесено: {moved}. Об’єднано: {merged}. Пропущено: {skipped}.

---

## 4. Логіка `transferDistractorCards`

Файл: `src/learning/quiz/distractorTransfer.ts` (паритет `quicklingo/learning/quiz/distractor_transfer.py`).

```typescript
type DistractorTransferResult = {
  moved: number;
  merged: number;
  skipped: number;
};

transferDistractorCards(
  cardIds: number[],
  targetTag: string,
  direction: string,
  deckName?: string,
): DistractorTransferResult
```

**Правила (одна транзакція):**

1. `targetTag` trim, не порожній, **не** `__quiz-distractors`.
2. `targetDeck = getOrCreateDeck(deckName ?? targetTag, targetTag, direction)` — identity `tag|direction`.
3. Для кожної `cardId`:
   - Картка має бути в distractor deck (`isQuizDistractorDeck`) і `isQuizDistractorCard`.
   - Напрямок source deck = `direction` (resolved learning kind).
   - Дублікат у target: `lower(trim(front))` (як `normalizeSource` / upsert basic).
   - **Дублікат → merge:** доповнити `back`, `context`, `hint`, `notes` лише де в target порожнє; **DELETE** distractor card (+ tombstone sync).
   - **Немає дубліката → move:** `deck_id = target`, `card_type = 'basic'`, `next_review_date = today`, reset FSRS (`ease=2.5`, `interval_days=0`, `fsrs_state=''`, `last_reviewed=''`).
4. Повернути `{ moved, merged, skipped }`.

**Заборонені теги:** `__quiz-distractors` → все `skipped`.

---

## 5. Lookup після переносу

`lookupEnglishMetadata` ([`choice_lookup.ts`](quiz_distractor_mobile_prompt.md)) спочатку шукає в **user decks**, потім в distractor deck. Після переносу картка в основній колоді знаходиться **раніше** — очікуваний ефект для quiz wrong-choice hints.

---

## 6. Sync

Перенос = UPDATE/DELETE карток + можливий INSERT deck — стандартний merge `history.db` через WebDAV. Без змін у sync protocol.

---

## 7. i18n ключі (додати в mobile locales)

**Menu**

- `main.menu_distractor_decks`

**Browser**

- `learning.distractor_decks_search`
- `learning.distractor_decks_search_hint`
- `learning.distractor_decks_count`
- `learning.distractor_decks_col_review`
- `learning.distractor_decks_transfer_btn`

**Transfer dialog**

- `learning.distractor_decks_transfer_title`
- `learning.distractor_decks_transfer_hint`
- `learning.distractor_decks_target_tag`
- `learning.distractor_decks_target_name`
- `learning.distractor_decks_tag_placeholder`
- `learning.distractor_decks_name_placeholder`
- `learning.distractor_decks_transfer_none_selected`
- `learning.distractor_decks_transfer_tag_required`
- `learning.distractor_decks_transfer_done`

Реюз: `learning.deck`, `learning.card_front`, `learning.card_back`, `learning.card_hint`, `learning.card_notes`, `learning.delete_card`, `learning.quiz_questions_edit`, `learning.quiz_refresh`.

---

## 8. Файли mobile для орієнтації

| Область | Файли |
|---------|--------|
| DB | `src/db/learningRepository.ts` |
| Distractor helpers | `src/learning/quiz/distractorDeck.ts`, `normalize.ts` |
| Quiz UI | `app/(tabs)/learning/`, quiz session components |
| History tags | tag counts для combo переносу |
| Navigation | tools / settings stack |

---

## 9. Desktop reference (актуальні файли)

| Файл | Роль |
|------|------|
| `quicklingo/learning/quiz/distractor_transfer.py` | `transfer_distractor_cards`, `DistractorTransferResult` |
| `quicklingo/ui/widgets/distractor_cards_browser.py` | браузер таблиця |
| `quicklingo/ui/dialogs/distractor_transfer_dialog.py` | діалог тега/назви |
| `quicklingo/ui/distractor_decks_window.py` | вікно |
| `quicklingo/ui/main_window.py` | пункт меню |
| `tests/test_distractor_transfer.py` | тести move/merge/skip |

---

## 10. Критерії готовності mobile

- [ ] Пункт меню «Колоди дистракторів» при `learning.quiz`
- [ ] Список карток distractor deck по напрямку + пошук
- [ ] Мультивибір + edit/delete
- [ ] Діалог переносу з тегом (history + deck tags)
- [ ] `transferDistractorCards` — move + merge + delete distractor
- [ ] Заборона тега `__quiz-distractors`
- [ ] Sync перенесених карток
- [ ] Quiz lookup знаходить картку в основній колоді після переносу

---

## 11. Не в scope

- Help topic для дистракторів (desktop теж без help).
- Повторення AI-генерації дистракторів — вже в [`quiz_distractor_mobile_prompt.md`](quiz_distractor_mobile_prompt.md).
