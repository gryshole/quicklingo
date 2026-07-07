# QuickLingo

A lightweight Windows assistant for quick translation during online meetings and TV series, with built-in vocabulary learning.

**Download:** [Latest release](https://github.com/gryshole/quicklingo/releases/latest) (Windows zip)

## Features

### Translation

- **Always on Top** window (~18% of screen width, docked to the right)
- Multiple AI providers: **Groq**, **Google Gemini**, **OpenRouter**, **Mistral**, **Ollama** (local), **DeepSeek**, **OpenAI**, **Anthropic**
- Configurable **models**, **translation directions**, **profiles**, and **prompts**
- Global hotkeys: translate selection, translate clipboard, optional **global input** capture
- Response cache, auto-copy result, system tray, autostart
- Non-blocking UI during API requests
- Ctrl+/Ctrl- and mouse wheel zoom on input and result fields

### History

- Automatic SQLite history (`%APPDATA%/QuickLingo/history.db`)
- Search, filter, star, tag, and export requests (JSON, Markdown, meeting transcripts)
- Build vocabulary decks from translation history

### Learning

- **QuickLingoLearning.exe** — standalone learning app (same data folder as the main app)
- Spaced-repetition **review**, **quiz** sessions, and **AI deck** generation
- Corpus analysis from history, card images, TTS audio
- **Anki** export (`.apkg` / CSV)
- Progress dashboard with activity heatmap

### Other

- English / Ukrainian UI
- In-app updates (**Help → Check for updates**)
- API keys encrypted with Windows DPAPI (optional, in Settings → Features)

## Requirements

- Python 3.12+
- Windows 10/11

## Quick start (development)

```powershell
git clone https://github.com/gryshole/quicklingo.git
cd quicklingo
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the main app:

```powershell
python main.py
```

Run the learning app only:

```powershell
python -m quicklingo.learning_app
```

On first launch, open **Tools → Settings → API keys** and add key(s) for the providers you use. At minimum, configure **Groq** and/or **Gemini**:

- Groq: [console.groq.com](https://console.groq.com/)
- Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

Keys are saved in `%APPDATA%/QuickLingo/settings.json`.

## Download and updates

### First install

1. Download `QuickLingo-0.x.y-win64.zip` from [GitHub Releases](https://github.com/gryshole/quicklingo/releases/latest).
2. Unzip to a folder you can write to (e.g. `Documents\QuickLingo` or `%LOCALAPPDATA%\QuickLingo`). Avoid `Program Files` — in-app updates need write access.
3. Run `QuickLingo.exe` (translation) or `QuickLingoLearning.exe` (learning only).
4. Add API keys in **Tools → Settings → API keys**.

Your settings, history, decks, and config live in `%APPDATA%/QuickLingo/` and are **not** removed when you update the app folder.

### Sync between PCs (work / home)

QuickLingo can sync **only** `history.db` (translations, decks, cards, quiz data) between computers. Settings, API keys, card images, and audio stay local on each machine.

1. Open **Tools → Settings → Synchronization**.
2. Choose a transport:
   - **Google Drive**, **Dropbox**, or **OneDrive** — register your own OAuth app (client ID / app key), enter credentials in Settings, click **Connect…**, then sign in in the browser.
   - **WebDAV** — URL + username + password (no desktop sync client required).
3. On each PC, use **Tools → Sync database…** after you translate or study. The app merges remote changes, then uploads an updated snapshot.

**OAuth setup (one-time per provider):**

| Provider | Where to register | Redirect URI |
|----------|-------------------|--------------|
| Google Drive | [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth client (Desktop) | `http://127.0.0.1` |
| Dropbox | [Dropbox App Console](https://www.dropbox.com/developers/apps) — scoped access `files.content.read/write` | `http://127.0.0.1` |
| OneDrive | [Microsoft Entra](https://entra.microsoft.com/) → App registrations → Public client/native | `http://127.0.0.1` |

Enable **Drive API** (Google) and scope **Files.ReadWrite.AppFolder** (Microsoft). Files are stored in each provider's app-specific area (`appDataFolder` / app folder), not in your visible Drive root.

Deletes are preserved via tombstones so removed cards or translations do not reappear from the cloud. Conflicting edits use last-write-wins based on timestamps.

### In-app update (0.1.0+)

**Help → Check for updates → Update now** — downloads the latest release, replaces the app files, and restarts QuickLingo. You can also open the release page in the browser and unzip manually.

### For developers: publish a release

1. Bump `__version__` in `quicklingo/version.py`.
2. Commit, tag, and push:

```powershell
git tag v0.1.1
git push origin main --tags
```

GitHub Actions builds the Windows zip and attaches it to the release. The tag must match the version in `version.py`.

## Usage

1. Choose a **model** and **direction** from the dropdowns.
2. Type text and press **Enter**.
3. The result appears in the output field; the request is saved to history automatically.

Use **Tools → Settings** to manage API keys, models, features, learning options, directions, and profiles. All configuration is editable in the UI — no manual JSON editing required.

| Menu | Description |
|------|-------------|
| **Tools → Settings** | Full configuration dialog |
| **Tools → Sync database…** | Merge and upload history to a sync folder or WebDAV |
| **Tools → Request history** | Browse, search, and export past translations |
| **Study → Learning** | Decks, review, quiz, stats |
| **Tools → Quiz questions** | Manage AI-generated quiz questions |
| **Help** | About, updates, and in-app documentation |

### UI language

The interface defaults to **English**. Switch to Ukrainian via **Tools → Settings → Interface**; changes apply immediately when you click **Apply** or **OK**.

## Configuration

On first run, QuickLingo copies the distribution `config_data/` into `%APPDATA%/QuickLingo/config/`. The app reads and writes config there automatically when you use **Settings**.

### Settings tabs

| Tab | What you can do |
|-----|-----------------|
| **Interface** | Choose UI language (English / Ukrainian) |
| **API keys** | Provider API keys and Ollama base URL |
| **Models** | Enable/disable models in the main window dropdown |
| **Features** | Always on top, hotkeys, tray, cache, history, encrypted keys |
| **Learning** | SRS limits, quiz settings, AI prompts for cards and quizzes |
| **Synchronization** | WebDAV or cloud API (Google Drive, Dropbox, OneDrive) for `history.db` |
| **Directions** | Add, edit, delete, enable/disable translation directions |
| **Profiles** | Edit prompts and formatters per direction; add/delete profiles |

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

Prompt bodies live in `.txt` files under `prompts/`. Keep output conventions aligned with the chosen formatter.

### Formatters

Built-in formatters ship in `config_data/formatters/`:

| Formatter ID | Engine | Use case |
|--------------|--------|----------|
| `ua_en_cards` | `builtin:ua_en_cards` | Structured cards for Ukr → Eng |
| `en_ua_cards` | `builtin:en_ua_cards` | Structured cards for Eng → Ukr |
| `plain` | `builtin:plain` | Simple escaped HTML with `<br>` |

### Default profiles

- **detailed** (default) — full explanations, context notes, and card layout
- **concise** — shorter prompts and plain text output

### Adding a direction

Use **Tools → Settings → Directions → Add**, then assign the direction to a profile under the **Profiles** tab.

## Build (Windows app folder)

```powershell
build.bat
```

Output: `dist/QuickLingo/` — a folder with:

- `QuickLingo.exe` — main translation app
- `QuickLingoLearning.exe` — standalone learning app
- `QuickLingoUpdater.exe` — used by in-app updates
- `_internal/`, `config_data/`

Zip this folder for distribution. **Onedir** starts much faster than a single self-extracting exe.

## Project structure

```
config_data/              Distribution defaults (copied to APPDATA on first run)
quicklingo/
├── app.py                Main app bootstrap
├── learning_app.py       Learning-only bootstrap
├── config/               Config loader, models, formatter registry
├── db/                   SQLite (history + learning)
├── features/             Feature flags and settings
├── i18n/                 English / Ukrainian strings
├── learning/             SRS, quiz, Anki export, TTS, AI deck generator
├── providers/            Groq, Gemini, OpenRouter, Mistral, Ollama, etc.
├── ui/
│   ├── main_window.py    Main translation window
│   ├── history_window.py Request history
│   ├── learning_window.py Decks, review, quiz, stats
│   ├── settings_dialog.py Settings editor (tabs)
│   └── settings/         Individual settings tabs
├── update/               In-app update checker and installer
└── workers/              Async QThread workers
```

## Security

See [SECURITY.md](SECURITY.md) for how to report vulnerabilities.

## Extending

- **New AI provider:** add a class under `providers/` and register it in `registry.py`
- **Custom formatter:** add a function in `format_output.py` and register it in `config/formatter_registry.py`

## License

MIT — see [LICENSE](LICENSE).
