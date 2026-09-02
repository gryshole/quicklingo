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
| History tags | `quicklingo/learning/card_history_tags.py` |
| Create deck corpus | `quicklingo/learning/deck_corpus.py` (`loadDirectionCorpusCoverage`, `pendingCorpusRecords`) |
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
4. `UPDATE deck_id` + **`content_updated_at`** (UTC ISO, див. §9) — FSRS / `next_review_date` не змінюються.
5. **History tags** (паритет `card_history_tags.py`): для перекладу, пов’язаного з карткою (`source_record_id` або match `front` ↔ `source_text`/`result_text` у тому напрямку):
   - **додати** `targetTag` у `translation_tags` (тег створюється в `tags`, якщо новий);
   - **зняти** `sourceTag`, якщо він ≠ `targetTag` (напр. `tv` → `law-conflict`);
   - bump `translations.updated_at` для sync.
6. Toast/message `learning.deck_split_done`; reload decks + cards.

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
- [ ] Apply оновлює **history tags** (create target tag, remove source tag) + `translations.updated_at`.
- [ ] «Створити колоду»: pending candidates — **всі колоди напрямку** (`loadDirectionCorpusCoverage`), не лише deck з тим самим tag (картки в `law-conflict` не з’являються як «нові» для `tv`).
- [ ] Settings: 3 spins + custom prompt + reset builtin.
- [ ] Quiz на `card_id` після переносу.
- [ ] `ai_request_scope('learning.deck_split')` у логах.
- [ ] **Sync:** §7 — bump `content_updated_at` на move + merge `deck_id` (див. acceptance §7.5).

---

## 7. Синхронізація після deck split (обов’язковий паритет)

> **Критично.** Без цього блоку split на одному пристрої зникає після sync з іншого (картки лишаються, але повертаються в source deck). Desktop уже виправлено в `fb42d71` + `39ebdaa`.

### 7.1 Перенос карток (`moveCardsToDeck`)

При `UPDATE deck_id` **завжди** оновлюй `content_updated_at` — інакше sync не бачить зміну:

```typescript
const movedAt = new Date().toISOString().replace(/\.\d{3}Z$/, (m) =>
  m === ".000Z" ? "+00:00" : m,
); // або той самий helper, що utc_now_iso() на desktop

// Після перевірок skip (distractor, direction, duplicate front у target):
UPDATE learning_cards
SET deck_id = ?, content_updated_at = ?
WHERE id = ?
```

- Формат: **UTC ISO** (`2026-09-02T20:32:38+00:00`), не лише `datetime('now')` без timezone — для коректного LWW між пристроями.
- `sync_id` **не змінювати**; tombstone на move **не** створювати.
- Паритет: `quicklingo/learning/deck_split/move_cards.py`, `quicklingo/learning/card_history_tags.py`.

### 7.2 Merge карток при download (`mergeCards` / `_merge_cards`)

Identity: `sync_id`. Deck identity: `tag|direction`, не numeric `deck_id`.

**Insert** (картки немає локально): `deck_id` з remote deck tag/direction — як раніше.

**Update** (картка вже є локально):

1. **Content LWW** по `content_updated_at` — front, back, context, hint, notes, priority, phonetic, image_prompt, quiz_distractors.
2. **SRS LWW** окремо по `srs_updated_at`.
3. **Deck placement** (виправлення бага):
   - Якщо remote виграв content → оновити поля **і** `deck_id` з remote.
   - Інакше, якщо `(localDeckTag, localDirection) ≠ (remoteDeckTag, remoteDirection)` **і** remote `content_updated_at` ≥ local → **лише** `UPDATE deck_id` (текст картки не чіпати).
   - При **рівних** timestamp для deck placement → **remote** (tie-break на користь хмари при pull).

Паритет: `quicklingo/sync/merge.py` (`_merge_cards`), `quicklingo/sync/models.py` (`_parse_sync_ts`, `_pick_side`, `_pick_remote_when_newer_or_tie`).

### 7.3 Порівняння timestamp

Не порівнювати рядки naïve (`'2026-09-02 17:38'` vs `'2026-09-02T20:32:38+00:00'`). Парсити обидва формати в UTC `Date` і порівнювати значення.

### 7.4 Upload / конфлікт між пристроями

- Sync = **merge remote → local**, потім **upload повного snapshot** (`history.snapshot.db`). Останній upload перезаписує файл у хмарі цілком.
- Пристрій з **новим split** має мати **новіший** `content_updated_at` на перенесених картках — тоді після merge інший пристрій отримає правильні колоди.
- **Порядок:** спочатку sync на ПК, де зробили split і застосували перенос; потім на інших (з тим самим кодом merge). Старий клієнт без §7.2 може знову перезаписати хмару старим розкладом колод.
- `deck_id` не входить у upload stats окремо — важливий саме bump `content_updated_at` на move.

### 7.5 Acceptance (sync)

- [ ] `moveCardsToDeck` bump `content_updated_at` (UTC ISO).
- [ ] `moveCardsToDeck` sync history tags (`add` target, `remove` source) + `translations.updated_at`.
- [ ] Merge застосовує remote `deck_id` при content win **або** при новішому/рівному remote timestamp при різних колодах.
- [ ] Timestamp parse: SQLite `YYYY-MM-DD HH:MM:SS` + ISO з offset.
- [ ] Після split на A + sync → на B pull дає ті самі `tag`/`count` по колодах (без ручного re-split).
- [ ] Тести-паритет: `tests/test_sync_merge.py` (`test_merge_applies_remote_deck_move`, `test_merge_applies_remote_deck_on_equal_timestamp_tie`), `tests/test_deck_split.py` (`test_move_cards_bumps_content_updated_at`, `test_move_cards_updates_history_tags`), `tests/test_deck_corpus.py`.

### 7.6 Діагностика sync після split

| Симптом | Причина |
|---------|---------|
| Split ок локально, після sync колоди «злітають» | merge не оновлює `deck_id`; або move без bump `content_updated_at` |
| На іншому пристрої картки в старій колоді | той пристрій sync **після** і перезаписав snapshot; або старий клієнт без §7.2 |
| Дублікати одного `front` у двох колодах | merge insert + старий рядок у source deck; прибрати дубль у зайвій колоді |
| `law-conflict` порожня в хмарі, локально 27 | ще не було upload з пристрою, де зробили split |
| Слова в «Створити колоду» для `tv` після split | history tag ще `tv` або pending лише по deck `tv` — §4.5 + `deck_corpus` direction-wide |
| Тег `law-conflict` не в dropdown перекладу | move без history tags — §4.5 |

---

## 8. MVP — не в scope (v2)

- Ручне переміщення слів між опціями (чекбокси).
- Apply **всі** опції одним кліком.
- Undo merge колод.

---

## 9. Діагностика AI (desktop)

Логи: `%APPDATA%\QuickLingo\logs\ai_requests.log`, purpose `learning.deck_split`.

Типові проблеми:

| Симптом | Причина |
|---------|---------|
| `EMPTY_RESPONSE` | провайдер не повернув текст (Groq TPM/RPM, обрізання) — retry / інша модель |
| Truncated JSON (`response_chars` мало) | великий deck; менший payload (front+back only) зменшує ризик |
| «no cards recovered» (legacy) | старий парсер з corpus regex — на mobile використати `loadDeckSplitJson` |
