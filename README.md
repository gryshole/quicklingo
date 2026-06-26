# QuickLingo

A lightweight Windows assistant for quick translation during online meetings and TV series.

## Features

- **Always on Top** window (~18% of screen width, docked to the right)
- Translation via **Groq API** (Llama 3.1 8B / 3.3 70B) and **Google Gemini** (2.5 Flash / 2.5 Flash Lite)
- Directions: **Укр → Англ** (meetings) and **Англ → Укр** (series)
- Configurable **translation profiles** and **prompts** via JSON/text files
- Automatic history in **SQLite** (`%APPDATA%/QuickLingo/history.db`)
- Non-blocking UI during API requests
- Ctrl+/Ctrl- and mouse wheel zoom on input and result fields

## Requirements

- Python 3.12+
- Windows 10/11

## Quick start

```powershell
cd quicklingo
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add your API key(s):

```
GROQ_API_KEY=gsk_xxxxxxxx
GEMINI_API_KEY=AIza_xxxxxxxx
```

- Groq: [console.groq.com](https://console.groq.com/)
- Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

Run:

```powershell
python main.py
```

## Usage

1. Choose a model from the dropdown.
2. Choose a translation direction.
3. Type text and press **Enter**.
4. The result appears in the output field; the request is saved to history automatically.

Use **Tools → Settings** to manage translation directions, profiles, prompts, formatters, and active profile selection. All configuration is editable in the UI — no manual JSON editing required.

### UI language

The interface defaults to **English**. Switch to Ukrainian via **Tools → Settings → Interface**; changes apply immediately when you click **Apply** or **OK**.

## Configuration

On first run, QuickLingo copies the distribution `config_data/` into `%APPDATA%/QuickLingo/config/`. The app reads and writes config there automatically when you use **Settings**.

### Settings tabs

| Tab | What you can do |
|-----|-----------------|
| **Interface** | Choose UI language (English / Ukrainian) |
| **Usage** | Pick active profile per direction |
| **Directions** | Add, edit, delete, enable/disable translation directions |
| **Profiles** | Edit prompts, temperature, formatters per direction; add/delete profiles |
| **Formatters** | Create formatters from presets or custom `rules:v1` pipelines with live preview |

Distribution ships `config_data/` next to `QuickLingo.exe` (project root in dev). It seeds an empty user config folder on first run only.

### Directions

Each direction JSON defines:

- `id` — internal key (e.g. `ua-en`)
- `label` — UI label (e.g. `Укр → Англ`)
- `source_lang` / `target_lang`
- `default_profile` — profile used when none is saved in settings
- `enabled` — show in the main window when `true`

### Profiles

Each profile JSON defines:

- `id`, `name`, `description`
- `prompts` — map of direction ID → prompt file path (relative to config root)
- `formatters` — map of direction ID → formatter ID
- `temperature` — optional API temperature (default `0.2`)

### Prompts

Prompt bodies live in `.txt` files under `prompts/`. Keep output conventions aligned with the chosen formatter (see below).

### Formatters

Formatters can use built-in presets (`builtin:plain`, `builtin:ua_en_cards`, `builtin:en_ua_cards`) or custom **`rules:v1`** pipelines edited in the **Formatters** tab.

| Formatter ID   | Engine                 | Use case                          |
|-----|------------------------|-----------------------------------|
| `ua_en_cards`  | `builtin:ua_en_cards`  | Structured cards for Ukr → Eng    |
| `en_ua_cards`  | `builtin:en_ua_cards`  | Structured cards for Eng → Ukr    |
| `plain`        | `builtin:plain`        | Simple escaped HTML with `<br>`   |

### Default profiles

- **detailed** (default) — full explanations, context notes, and card layout. Matches the original QuickLingo behavior.
- **concise** — shorter prompts and plain text output. Available in Preferences but not active by default.

A fresh install with default settings behaves exactly like the pre-config QuickLingo app.

### Adding a direction

Use **Tools → Settings → Directions → Add**, then add the direction to a profile under the **Profiles** tab.

## Build (.exe)

```powershell
build.bat
```

Or manually:

```powershell
pip install pyinstaller pillow
python scripts\make_icon.py
pyinstaller --onefile --windowed --name QuickLingo ^
    --icon assets\quicklingo_icon.ico ^
    --add-data "assets;assets" ^
    --collect-all PySide6 ^
    main.py
xcopy /E /I /Y config_data dist\config_data
```

Output: `dist/QuickLingo.exe` and `dist/config_data/` — keep both in the same folder.

Place `.env` next to the executable or set `GROQ_API_KEY` / `GEMINI_API_KEY` as environment variables.

## Project structure

```
config_data/              Distribution defaults (copied to APPDATA on first run)
quicklingo/
├── app.py                Bootstrap
├── config/               Config loader, models, formatter registry
├── ui/
│   ├── main_window.py    Main interface
│   ├── settings_dialog.py    Full settings editor (tabs)
│   ├── settings/             Directions, profiles, formatters tabs
│   └── format_output.py  Built-in HTML formatters
├── db/history.py         SQLite history
├── providers/            Groq, Gemini
├── prompts.py            Thin wrapper over config loader
└── workers/              Async QThread worker
```

## Extending

- **New AI provider:** add a class under `providers/` and register it in `registry.py`
- **Custom formatter:** add a function in `format_output.py` and register it in `config/formatter_registry.py`
- **Future:** Anki export and word frequency stats from history
