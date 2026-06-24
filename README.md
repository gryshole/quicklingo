# QuickLingo

Легкий Windows-асистент для швидкого перекладу під час онлайн-мітингів та перегляду серіалів.

## Можливості

- Вікно **Always on Top** (~18% ширини екрана, праворуч)
- Переклад через **Groq API** (Llama 3.1 8B / 3.3 70B) та **Google Gemini** (2.5 Flash / 2.5 Flash Lite)
- Напрямки: **Укр → Англ** (мітинги) та **Англ → Укр** (серіали)
- Автозбереження історії в **SQLite** (`%APPDATA%/QuickLingo/history.db`)
- Неблокуючий UI під час запитів до API

## Вимоги

- Python 3.12+
- Windows 10/11

## Швидкий старт

```powershell
cd quicklingo
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Відредагуйте `.env` і вставте свій ключ:

```
GROQ_API_KEY=gsk_xxxxxxxx
GEMINI_API_KEY=AIza_xxxxxxxx
```

- Groq: [console.groq.com](https://console.groq.com/)
- Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

Запуск:

```powershell
python main.py
```

## Використання

1. Оберіть модель у dropdown.
2. Оберіть напрямок перекладу.
3. Введіть текст і натисніть **Enter**.
4. Результат з'явиться у великому полі внизу; запит автоматично збережеться в БД.

## Збірка в .exe

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name QuickLingo main.py
```

Готовий файл: `dist/QuickLingo.exe`

> Для exe покладіть `.env` поруч з файлом або встановіть змінні `GROQ_API_KEY` / `GEMINI_API_KEY`.

## Структура проекту

```
quicklingo/
├── app.py              # Bootstrap
├── ui/main_window.py   # Інтерфейс
├── db/history.py       # SQLite
├── providers/          # Groq, Gemini та майбутні провайдери
├── prompts.py          # Динамічні промпти
└── workers/            # Async QThread worker
```

## Розширення

- Новий AI-провайдер: додайте клас у `providers/`, зареєструйте в `registry.py`
- Майбутнє: експорт історії в Anki та частотна статистика слів
