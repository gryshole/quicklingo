# QuickLingo

A lightweight Windows assistant for quick translation during online meetings and TV series.

**Download:** [Latest release](https://github.com/gryshole/quicklingo/releases/latest) (Windows zip)

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
```

Run:

```powershell
python main.py
```

On first launch, open **Tools → Settings → API keys** and add your key(s):

- Groq: [console.groq.com](https://console.groq.com/)
- Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

Keys are saved in `%APPDATA%/QuickLingo/settings.json`.

## Download and updates

### First install

1. Download `QuickLingo-0.x.y-win64.zip` from [GitHub Releases](https://github.com/gryshole/quicklingo/releases/latest).
2. Unzip to a folder you can write to (e.g. `Documents\QuickLingo` or `%LOCALAPPDATA%\QuickLingo`). Avoid `Program Files` — in-app updates need write access.
3. Run `QuickLingo.exe`.
4. Add API keys in **Tools → Settings → API keys**.

Your settings, history, and config live in `%APPDATA%/QuickLingo/` and are **not** removed when you update the app folder.

### In-app update (0.1.0+)

**Help → Check for updates → Update now** — downloads the latest release, replaces the app files, and restarts QuickLingo. You can also open the release page in the browser and unzip manually.

### For developers: publish a release

1. Bump `__version__` in `quicklingo/version.py`.
2. Commit, tag, and push:

```powershell
git tag v0.2.0
git push origin main --tags
```

GitHub Actions builds the Windows zip and attaches it to the release.

## Usage

1. Choose a model from the dropdown.
2. Choose a translation direction.
3. Type text and press **Enter**.
4. The result appears in the output field; the request is saved to history automatically.

Use **Tools → Settings** to manage API keys, translation directions, profiles, prompts, formatters, and active profile selection. All configuration is editable in the UI — no manual JSON editing required.

### UI language

The interface defaults to **English**. Switch to Ukrainian via **Tools → Settings → Interface**; changes apply immediately when you click **Apply** or **OK**.

## Configuration

On first run, QuickLingo copies the distribution `config_data/` into `%APPDATA%/QuickLingo/config/`. The app reads and writes config there automatically when you use **Settings**.

### Settings tabs

| Tab | What you can do |
|-----|-----------------|
| **Interface** | Choose UI language (English / Ukrainian) |
| **API keys** | Groq and Gemini API keys |
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

## Build (Windows app folder)

```powershell
build.bat
```

Output: `dist/QuickLingo/` — a folder with `QuickLingo.exe`, `QuickLingoUpdater.exe`, `_internal/`, and `config_data/`. Zip this folder for distribution; **onedir** starts much faster than a single self-extracting exe.

Manual build:

```powershell
pip install pyinstaller pillow
python scripts\make_icon.py
pyinstaller --noconfirm --clean QuickLingo.spec
pyinstaller --noconfirm --clean QuickLingoUpdater.spec
copy dist\QuickLingoUpdater.exe dist\QuickLingo\
xcopy /E /I /Y config_data dist\QuickLingo\config_data
```

Keep `config_data` next to `QuickLingo.exe`. After first run, add API keys via **Tools → Settings → API keys**.

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
