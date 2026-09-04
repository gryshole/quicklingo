# TODO: синхронізація навчальної статистики

> **Статус:** відкладено (не в пріоритеті зараз)  
> **Причина відкладення:** на пристроях багато «шумових» записів — кліки для перевірки UI/дизайну, тестові review і квізи. Синхронізація логів зараз змішала б реальний прогрес із тестовими даними.

## Поточна поведінка sync

| Дані | Синхронізується? | Де живе |
|------|------------------|---------|
| Стан картки (SRS): `next_review_date`, `interval_days`, `ease`, `fsrs_state`, `last_reviewed` | **Так** | `learning_cards` + merge по `srs_updated_at` |
| Контент картки, колода, переклади, quiz questions | **Так** | merge у `quicklingo/sync/merge.py` |
| Історія повторень | **Ні** | `review_logs` |
| Історія квізів | **Ні** | `quiz_logs` |
| Агрегати в UI (кількість review, quiz %, «сьогодні повторені») | **Ні** (локально з логів) | `get_card_review_stats`, `list_reviewed_cards_today` |

Після sync на другому ПК **черга review коректна**, але **статистика з першого ПК не підтягується**.

## Ціль (коли будемо робити)

Синхронізувати **повну навчальну статистику** між desktop / mobile / WebDAV так само надійно, як зараз синхронізуються картки:

1. **Merge `review_logs`** між пристроями (ідентифікація події, без дублікатів).
2. **Merge `quiz_logs`** (відповіді в квізі, `question_id`, `choices_shown`).
3. **Паритет UI:** лічильники на вкладці «Картки», «сьогодні повторені», quiz coverage — однакові після sync на будь-якому клієнті.
4. **Документація** для mobile (`quicklingomobile`) — той самий merge-контракт.

## Що врахувати перед імплементацією

- **Шумові дані:** очистити або відфільтрувати тестові логи на dev-машинах; можливо не синхронізувати записи старше N днів або з певного `device_id`.
- **Ключі:** `review_logs` зараз без `sync_id` — потрібен стабільний ключ події (наприклад `device_id` + `card sync_id` + `reviewed_at` + `rating`) або нова колонка `sync_id` / `event_id`.
- **Конфлікти:** LWW по timestamp або append-only merge (обидва логи зберігаються, якщо різні `event_id`).
- **Видалення:** tombstones для логів (якщо колода/картка видалена) — узгодити з `sync_tombstones`.
- **Обсяг:** snapshot вже повний; merge лише додає таблиці — перевірити розмір WebDAV snapshot після років логів.
- **Тести:** паритет `tests/test_sync_merge.py` + фікстури з двома «пристроями».

## Орієнтовні кроки (чернетка)

1. Схема: `sync_id` / `event_id` для `review_logs` і `quiz_logs` (міграція).
2. `_merge_review_logs` / `_merge_quiz_logs` у `merge.py`; оновити `compute_upload_stats`.
3. При `record_review` / `batch_insert_quiz_logs` — заповнювати `device_id` + UTC timestamp (як на картках).
4. UI smoke: після sync на другому клієнті збігаються `review_count` і quiz stats.
5. Mobile prompt або внутрішній чеклист паритету (якщо знову буде окремий doc).

## Коли повертатися до задачі

- Після стабілізації UI (менше «кліків для дизайну» у прод-даних).
- Коли потрібна **однакова статистика** на ПК + телефон + другий ПК без ручного експорту.

## Пов’язаний код

- `quicklingo/sync/merge.py` — `_merge_cards` (SRS уже є)
- `quicklingo/db/learning_reviews.py` — `review_logs`
- `quicklingo/db/learning_quiz.py` — `quiz_logs`
- `quicklingo/db/learning_cards.py` — `get_card_review_stats`
