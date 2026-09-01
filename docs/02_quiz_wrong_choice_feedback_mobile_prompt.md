# 02 — Feedback після помилки в квізі — промпт для quicklingomobile

> **02 з 02** — після [01_distractor_decks_mobile_prompt.md](01_distractor_decks_mobile_prompt.md) (або паралельно, якщо браузер колод не потрібен). Зміст кроків: [README](README.md).

Скопіюй цей текст у чат для `d:\Develop\quicklingomobile`, коли базовий квіз і distractor lookup уже є на mobile.

---

## Задача: паритет з desktop — комбінований feedback для `definition_match` і `fill_blank`

**Контекст:** React Native + Expo, quiz screen (`app/(tabs)/learning/quiz.tsx` або аналог). Після неправильного вибору варіанта показується текст під кнопками (desktop: `QuizSession` → `_choice_feedback_label`).

**Ціль:** Для типів **`definition_match`** і **`fill_blank`** замінити старий однорядковий hint лише про хибний варіант на **комбінований** рядок: про **цільове слово** + про **обраний дистрактор**.

**Desktop reference:** `quicklingo/learning/quiz/choice_lookup.py` (`formatWrongChoiceFeedback`), `quicklingo/ui/widgets/quiz_session.py` (`_on_choice_clicked`, `_populate_wrong_table`).

---

## 1. Коли застосовувати

| `question_type` | Feedback |
|-----------------|----------|
| `definition_match` | **Комбінований** рядок (§3.1) |
| `fill_blank` | **Комбінований** рядок (§3.3) |
| `translation_recall` | Старий формат: лише обраний варіант |

Комбінований формат — **тільки** якщо для `correct_english` знайдено metadata з непорожнім `ukrainian`.

---

## 2. Lookup (без змін)

Використовуй існуючий `lookupEnglishMetadata(english, direction)`:

1. Спочатку **user decks** (не distractor)
2. Потім **distractor deck** (`__quiz-distractors`)
3. Ключ: `normalizeEnglishQuizKey(english)` (статті `the` / `a` / `an`)

Поля metadata: `english`, `ukrainian`, `definition`, `cardId`, `fromDistractorDeck`.

---

## 3. Функція `formatWrongChoiceFeedback`

Сигнатура (паритет desktop):

```typescript
function formatWrongChoiceFeedback(
  selectedEnglish: string,
  direction: string,
  options?: {
    correctEnglish?: string;
    questionType?: "fill_blank" | "definition_match" | "translation_recall";
  },
): string | null
```

### 3.1 `definition_match` + є `correctEnglish`

1. `correctMeta = lookupEnglishMetadata(correctEnglish, direction)`
2. Якщо `correctMeta?.ukrainian` непорожній:
   - `selectedMeta = lookupEnglishMetadata(selectedEnglish, direction)`
   - `selectedLabel = selectedMeta.ukrainian` або (fallback) `selectedMeta.definition`
   - Якщо `selectedLabel` є → i18n **`learning.quiz_wrong_choice_definition_match`**
   - Інакше → **`learning.quiz_wrong_choice_definition_match_unknown_selected`**

### 3.3 `fill_blank` + є `correctEnglish`

Та сама логіка що §3.1, інші i18n-ключі:

1. `correctMeta = lookupEnglishMetadata(correctEnglish, direction)`
2. Якщо `correctMeta?.ukrainian` непорожній:
   - `selectedMeta = lookupEnglishMetadata(selectedEnglish, direction)`
   - `selectedLabel = selectedMeta.ukrainian` або (fallback) `selectedMeta.definition`
   - Якщо `selectedLabel` є → i18n **`learning.quiz_wrong_choice_fill_blank`**
   - Інакше → **`learning.quiz_wrong_choice_fill_blank_unknown_selected`**

### 3.4 Інші випадки (fallback)

Як у desktop до зміни:

- metadata з `ukrainian` → `learning.quiz_wrong_choice_hint`
- лише `definition` → `learning.quiz_wrong_choice_definition`
- немає картки → `learning.quiz_wrong_choice_unknown`

---

## 4. i18n

Додати ключі (uk / en):

```json
"learning.quiz_wrong_choice_definition_match": "Питання стосувалось: {correct_ukrainian} ({correct_english}); твій вибір «{selected}» — це «{selected_ukrainian}».",
"learning.quiz_wrong_choice_definition_match_unknown_selected": "Питання стосувалось: {correct_ukrainian} ({correct_english}); твій вибір «{selected}»."
```

```json
"learning.quiz_wrong_choice_definition_match": "The question was about {correct_ukrainian} ({correct_english}); your choice «{selected}» means «{selected_ukrainian}».",
"learning.quiz_wrong_choice_definition_match_unknown_selected": "The question was about {correct_ukrainian} ({correct_english}); your choice was «{selected}»."
```

**Приклад (uk):**

> Питання стосувалось: сорочка (shirt); твій вибір «jacket» — це «куртка».

Плейсхолдери:

| Ключ | Джерело |
|------|---------|
| `correct_ukrainian` | metadata для `question.correctEnglish` |
| `correct_english` | `correctMeta.english` або `correctEnglish` |
| `selected` | текст обраної кнопки |
| `selected_ukrainian` | metadata обраного: `ukrainian`, інакше `definition` |

---

## 5. UI quiz screen

Після кліку на варіант (якщо `!correct`):

```typescript
const feedback = formatWrongChoiceFeedback(selected, sessionDirection, {
  correctEnglish: question.correctEnglish,
  questionType: question.type,
});
if (feedback) setChoiceFeedback(feedback);
```

- Один рядок, `wordWrap`, стиль як раніше (помаранчевий/secondary текст під choices).
- Кнопка «Далі» — без змін.
- Підсвітка: обраний — червоний, правильний — зелений (як зараз).

### Таблиця помилок після сесії

У summary / wrong-answers table колонка «Твій вибір» теж викликає `formatWrongChoiceFeedback` з `correctEnglish` + `questionType` — не лише `selected`.

---

## 6. Тести

1. **definition_match:** main deck `сорочка`/`shirt`, distractor `куртка`/`jacket` → feedback містить обидві пари.
2. **translation_recall:** старий формат «Твій вибір … — …».
3. **definition_match без ukrainian у correct:** fallback на старий hint для selected.
4. **selected без картки:** `definition_match_unknown_selected` (без «це …»).

---

## 7. Файли desktop для звірки

| Файл | Що дивитись |
|------|-------------|
| `quicklingo/learning/quiz/choice_lookup.py` | `format_wrong_choice_feedback`, `_selected_choice_label` |
| `quicklingo/ui/widgets/quiz_session.py` | виклики з `correct_english`, `question_type` |
| `quicklingo/i18n/locales/uk.json` | ключі `quiz_wrong_choice_*` |
| `tests/test_quiz_distractor_deck.py` | `test_format_wrong_choice_feedback_definition_match_combined` |

---

## 8. Не робити

- Не перекладати англійське definition-речення з промпта (`definition_match`) і **не перекладати** речення fill_blank з `prompt_text` — лише UA-пара з картки для `correctEnglish`.
- Не змінювати feedback для `translation_recall`.
- Не дублювати lookup: один `lookupEnglishMetadata` на обидва слова.

---

## 9. Розширення: `fill_blank` (комбінований feedback)

Після §3–4 для `definition_match` додати той самий патерн для **`fill_blank`**.

**Приклад (uk):**

> У пропуску: стілець (chair); твій вибір «shelf» — це «полиця».

Речення з прогалиною вже на екрані англійською — feedback лише пояснює **слово в пропуску** та **хибний варіант**, без перекладу всього речення.

### i18n (додатково до §4)

```json
"learning.quiz_wrong_choice_fill_blank": "У пропуску: {correct_ukrainian} ({correct_english}); твій вибір «{selected}» — це «{selected_ukrainian}».",
"learning.quiz_wrong_choice_fill_blank_unknown_selected": "У пропуску: {correct_ukrainian} ({correct_english}); твій вибір «{selected}»."
```

```json
"learning.quiz_wrong_choice_fill_blank": "In the blank: {correct_ukrainian} ({correct_english}); your choice «{selected}» means «{selected_ukrainian}».",
"learning.quiz_wrong_choice_fill_blank_unknown_selected": "In the blank: {correct_ukrainian} ({correct_english}); your choice was «{selected}»."
```

Реалізація в `formatWrongChoiceFeedback`: спільний helper `_combinedWrongChoiceFeedback` з різними `matchKey` / `unknownSelectedKey` для `definition_match` і `fill_blank` (паритет `_combined_wrong_choice_feedback` у desktop).

---

## 10. Тести (додатково)

5. **fill_blank:** main `стілець`/`chair`, distractor `полиця`/`shelf` → feedback містить обидві пари.
6. **fill_blank, selected без картки:** `fill_blank_unknown_selected`.

---

## 11. Desktop helper

| Функція | Призначення |
|---------|-------------|
| `_combined_wrong_choice_feedback` | lookup correct + selected, вибір i18n-ключа |
| `format_wrong_choice_feedback` | маршрутизація за `question_type` |
