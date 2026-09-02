# 03 — AI-розділення колоди на підтеги — промпт для quicklingomobile

> **03** — новий крок. Зміст кроків: [README](README.md).

Скопіюй цей текст у чат для `d:\Develop\quicklingomobile`, коли **базове learning, decks, AI providers** уже є на mobile.

---

## Задача: паритет з desktop — AI-аналіз великої колоди + варіанти розділення

**Контекст:** React Native + Expo. Learning повторює desktop: decks, cards, FSRS, quiz.

**Ціль:** На вкладці **Картки** додати **«Розділити колоду…»** для колод з ≥ N карток (не distractor deck). AI аналізує колоду, показує **список варіантів** (тег + підгрупа слів), користувач **вибирає одну** або **«Не розділяти»**, може **редагувати tag/deck_name**, потім **перенос карток** у нову колоду. Quiz questions залишаються на `card_id`.

**Desktop reference:**

| Область | Файли |
|--------|--------|
| Core | `quicklingo/learning/deck_split/` (`models`, `prompts`, `parse`, `move_cards`, `service`) |
| Worker | `quicklingo/workers/ai_deck_split_worker.py` |
| UI | `deck_split_start_dialog.py`, `deck_split_options_dialog.py`, `learning_window.py` |
| Settings | `learning_features_tab.py`, `features/registry.py` |

---

## 1. Feature keys (`learning.deck_split`)

| Key | Default | Опис |
|-----|---------|------|
| `min_deck_cards` | `25` | Мін. карток у колоді, щоб кнопка активна |
| `max_options` | `4` | Макс. варіантів розділення від AI |
| `min_subgroup_cards` | `8` | Мін. карток у варіанті (після match) — **жорсткий** критерій |
| `split_prompt_template` | `""` | Кастомний system prompt; порожній → builtin |

Фіча **always-on** (без `enabled` toggle).

**Settings UI:** spins `min_deck_cards` (5–200), `max_options` (2–5), `min_subgroup_cards` (5–30) + prompt field з reset на builtin.

---

## 2. System prompt

### Побудова

- `getDeckSplitSystemPrompt(directionId)` — **напрямок колоди обов’язковий** (підстановка front/back language).
- Builtin або кастомний `split_prompt_template`.
- Плейсхолдери підставляються через **`.replace()`**, не `String.format` — у builtin є JSON-фігурні дужки.

### Плейсхолдери

| Placeholder | Опис |
|-------------|------|
| `{max_options}` | з settings |
| `{min_subgroup_cards}` | з settings |
| `{cards_description}` | «English on front, Ukrainian on back» або vice versa для `ua-en` |
| `{fronts_match_note}` | character-exact copy rule для `front` у відповідній мові |
| `{direction_label}` | human label напрямку (для кастомних промптів) |

### Builtin prompt (копіпаста)

Шаблон до підстановки плейсхолдерів:

```
You are an analyst helping organize vocabulary learning decks into coherent thematic subgroups.

The user message contains a deck with cards ({cards_description}).

Your task:
1. Read all cards and decide whether the deck mixes distinct themes (e.g. domains, registers, topics, idioms vs single words).
2. Propose 0 to {max_options} split options. Each option moves a thematic subgroup into a NEW deck with its own tag.
3. Target subgroup size: about 20–35 words per option when possible.
4. HARD limit: each option must list at least {min_subgroup_cards} words in "fronts". If a theme has fewer, do NOT include that option — merge into another theme or omit it.
5. Each word (each "front" string) may appear in exactly ONE option's "fronts". Never assign the same front to multiple options.
6. Words NOT listed in any option's "fronts" stay in the source deck.
7. If the deck is already cohesive, return "options": [] and explain in "summary".
8. If user_note is non-empty, use it as context (topic, source material, learner goal).

Fronts copying rules (critical):
- fronts ({fronts_match_note}).
- Wrong casing, lemmatized forms, or paraphrases will fail matching — copy-paste from input only.

Tag rules:
- lowercase, latin letters, digits, hyphens only
- logically related to source_tag (e.g. source "work" → "work-legal", "work-meetings", not bare "legal")
- must differ from source_tag
- never use "__quiz-distractors"

Each option needs: id (short letter), title (human label), tag, deck_name (display name), rationale (1–2 sentences), fronts (list of front strings obeying the rules above).

Respond with JSON only, no markdown:
{
  "summary": "short analysis",
  "options": [
    {
      "id": "a",
      "title": "...",
      "tag": "source-theme",
      "deck_name": "...",
      "rationale": "...",
      "fronts": ["exact front", ...]
    }
  ]
}
```

**LLM:** `temperature=0.2`, scope логів `learning.deck_split`.

### User message (JSON)

Тільки **front + back** на картку (без hint, definition, example — менше токенів; кластеризація по парі front/back).

```json
{
  "source_tag": "work",
  "direction": "en-ua",
  "direction_label": "Англ → Укр",
  "deck_name": "Work vocabulary",
  "user_note": "optional context from start dialog",
  "cards": [
    { "front": "compliance", "back": "згодність" },
    { "front": "traitor", "back": "зрадник" }
  ]
}
```

`buildDeckSplitUserMessage(deck, cards, userNote?)` — паритет `prompts.py`.

---

## 3. JSON-схема відповіді + парсинг

```typescript
type DeckSplitOption = {
  id: string;
  title: string;
  tag: string;
  deck_name: string;
  rationale: string;
  fronts: string[];
  card_ids: number[]; // after match_fronts_to_card_ids
};

type DeckSplitAnalysisResult = {
  summary: string;
  options: DeckSplitOption[];
  source_deck_id: number;
  source_tag: string;
  direction: string;
};
```

**Парсер** `parseDeckSplitResponse(raw, { deckId, sourceTag, direction })`:

1. **`loadDeckSplitJson(raw)`** — НЕ corpus `_salvage_cards_regex` (той шукає `front+back` objects і дає misleading «no cards recovered»).
2. Strip markdown fences → `JSON.parse`; fallback `_salvageDeckSplitTruncated` для обрізаного JSON з `options`.
3. Порожня відповідь → `Model returned an empty response…`
4. Невалідний JSON → `Could not parse AI response as deck-split JSON…`
5. Tag: lowercase `a-z0-9-`, не `__quiz-distractors`, ≠ `source_tag`.
6. Дедуп `fronts` між опціями (перший wins).
7. Фільтр: `len(matched card_ids) >= min_subgroup_cards`, `options.length <= max_options`.
8. `matchFrontsToCardIds(deckId, fronts)` через `normalizeSource(front)` (паритет distractor transfer).

---

## 4. UI flow (desktop parity)

### Кнопка на вкладці Картки

- `learning.deck_split_btn` — «Розділити колоду…» (secondary, поруч з export).
- Enabled: `countCards >= min_deck_cards`, не distractor deck, worker не busy.

### Аналіз (busy state)

- Під час worker: синій callout **«Аналіз колоди…»** + Cancel на вкладці Картки.
- Worker cancel → `finished(null)`, UI скидається без діалога.

### Діалог 1 — запуск (`DeckSplitStartDialog`)

- Інфо: name, tag, direction, count (`learning.deck_split_start_info`).
- Опційне поле **Контекст** → `user_note`.
- Model combo → OK запускає `AiDeckSplitWorker`.

### Діалог 2 — варіанти (`DeckSplitOptionsDialog`)

Сучасний layout (паритет desktop):

- **Summary callout** — блідо-синій блок, rounded, muted text.
- **Selectable cards** (не QListWidget): клікабельні плитки, hover, активна — синя рамка + маркер ●.
- Перший варіант: **«Не розділяти»** (`learning.deck_split_option_none`) — default.
- Опції: `learning.deck_split_option_item` (title · tag · count), tooltip = rationale.
- **Tag / deck name** — лейбли над полями, rounded inputs, focus ring.
- **Preview table** — front/back, чиста таблиця (horizontal dividers, sticky-style header).
- Footer: **Cancel** (ghost) + **«Перенести в обрану колоду»** (primary); Apply disabled для «Не розділяти».

### Apply

```typescript
type MoveCardsResult = { moved: number; skipped: number };

moveCardsToDeck(
  cardIds: number[],
  targetTag: string,
  direction: string,
  deckName?: string,
): MoveCardsResult
```

1. `targetTag` trim, lowercase; порожній / `__quiz-distractors` → skip all.
2. `getOrCreateDeck(deckName ?? targetTag, targetTag, direction)`.
3. Skip: missing card, distractor source deck, direction mismatch, duplicate `front` у target.
4. `UPDATE deck_id` only — FSRS / `next_review_date` не змінюються.
5. Toast/message `learning.deck_split_done`; reload decks + cards.

---

## 5. i18n keys

- `learning.deck_split_btn`, `deck_split_title`, `deck_split_start_info`
- `deck_split_note_label`, `deck_split_note_placeholder`
- `deck_split_options_title`, `deck_split_option_none`, `deck_split_option_item`
- `deck_split_apply`, `deck_split_done`, `deck_split_analyzing`
- `settings.features.deck_split_min_cards`, `deck_split_max_options`, `deck_split_min_subgroup`, `deck_split_prompt`
- Reuse: `learning.distractor_decks_target_tag`, `distractor_decks_target_name`, `card_front`, `card_back`, `learning.model`, `main.cancel`

---

## 6. Acceptance checklist

- [ ] Кнопка активна при ≥ `min_deck_cards`, не distractor deck.
- [ ] Busy callout + cancel під час AI; empty/truncated response — зрозуміла помилка, не «no cards recovered».
- [ ] User payload: лише `front` + `back`; system prompt з direction-aware placeholders.
- [ ] Парсер deck-split JSON (не corpus salvage).
- [ ] Унікальність fronts між опціями; `min_subgroup_cards` жорсткий; character-exact match.
- [ ] Options UI: callout, card tiles, tag/name fields, preview table, primary/ghost footer.
- [ ] «Не розділяти» — close без змін у DB.
- [ ] Apply + skip duplicates; не з distractor / не в distractor tag.
- [ ] Settings: 3 spins + custom prompt + reset builtin.
- [ ] Quiz на `card_id` після переносу.
- [ ] `ai_request_scope('learning.deck_split')` у логах.

---

## 7. MVP — не в scope (v2)

- Ручне переміщення слів між опціями (чекбокси).
- Apply **всі** опції одним кліком.
- Undo merge колод.

---

## 8. Діагностика (desktop)

Логи: `%APPDATA%\QuickLingo\logs\ai_requests.log`, purpose `learning.deck_split`.

Типові проблеми:

| Симптом | Причина |
|---------|---------|
| `EMPTY_RESPONSE` | провайдер не повернув текст (Groq TPM/RPM, обрізання) — retry / інша модель |
| Truncated JSON (`response_chars` мало) | великий deck; менший payload (front+back only) зменшує ризик |
| «no cards recovered» (legacy) | старий парсер з corpus regex — на mobile використати `loadDeckSplitJson` |
