from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from quicklingo.i18n import tr
from quicklingo.version import __version__

HELP_TOPICS = (
    "about",
    "models",
    "directions_profiles",
    "features",
    "history",
    "quiz_questions",
    "learning",
    "sync",
    "sync_google_drive",
)

_HEADING_EMOJI = {
    # About — Ukrainian
    "Що таке QuickLingo": "👋",
    "Як це працює": "⚙️",
    "Ключові поняття": "🧠",
    "Типові сценарії": "🎯",
    "Налаштування та дані": "🛠",
    "Де почати": "🚀",
    # About — English
    "What is QuickLingo": "👋",
    "What QuickLingo is": "👋",
    "How it works": "⚙️",
    "Key concepts": "🧠",
    "Typical scenarios": "🎯",
    "Typical use cases": "🎯",
    "Settings and data": "🛠",
    "Where to start": "🚀",
    "Getting started": "🚀",
    # Models — Ukrainian
    "Загальна ідея": "💡",
    "Ключі API": "🔑",
    "Підтримуються провайдери": "🤖",
    "Список моделей": "📋",
    "Додавання моделі вручну": "➕",
    "Як модель використовується при перекладі": "🔄",
    "Як обрати модель": "🎯",
    # Models — English
    "General idea": "💡",
    "The big picture": "💡",
    "API keys": "🔑",
    "Supported providers": "🤖",
    "Model list": "📋",
    "List of models": "📋",
    "Adding a model manually": "➕",
    "How a model is used when translating": "🔄",
    "Choosing a model": "🎯",
    # Profiles / directions — Ukrainian
    "Навіщо три вкладки": "🗂",
    "Напрямки (Інструменти → Налаштування → Напрямки)": "🧭",
    "Поля напрямку": "📝",
    "Профілі (Інструменти → Налаштування → Профілі)": "🎭",
    "Що налаштовується в профілі": "🧩",
    "Використання (Інструменти → Налаштування → Використання)": "🔗",
    "Приклад: серіали і робота": "🎬",
    "Крок 1 — два напрямки (вкладка Напрямки)": "1️⃣",
    "Крок 2 — профілі (вкладка Профілі). Можна так": "2️⃣",
    "Варіант А — окремі профілі": "🅰️",
    "Крок 3 — використання (вкладка Використання)": "3️⃣",
    "Крок 4 — глосарій (окремо, вкладка Глосарій)": "4️⃣",
    "Типовий робочий процес": "🔄",
    "Поради": "💬",
    # Profiles / directions — English
    "Why three tabs": "🗂",
    "Directions (Tools → Settings → Directions)": "🧭",
    "Direction fields": "📝",
    "Profiles (Tools → Settings → Profiles)": "🎭",
    "What you configure in a profile": "🧩",
    "Usage (Tools → Settings → Usage)": "🔗",
    "Example: series vs work": "🎬",
    "Step 1 — two directions (Directions tab)": "1️⃣",
    "Step 2 — profiles (Profiles tab). For example": "2️⃣",
    "Option A — separate profiles": "🅰️",
    "Step 3 — usage (Usage tab)": "3️⃣",
    "Step 4 — glossary (separate Glossary tab)": "4️⃣",
    "Typical workflow": "🔄",
    "Tips": "💬",
    # Features — Ukrainian
    "Що це за вкладка": "🎛️",
    "Як користуватися": "👆",
    "Загальне": "🪟",
    "Ввід": "⌨️",
    "Переклад": "🌐",
    "Історія та навчання": "📚",
    "Приватність": "🔒",
    "Як обрати набір функцій": "🎛️",
    "Зв’язок з іншими вкладками": "🔗",
    # Features — English
    "What this tab is": "🎛️",
    "How to use it": "👆",
    "General": "🪟",
    "Input": "⌨️",
    "Translation": "🌐",
    "History and learning": "📚",
    "Privacy": "🔒",
    "Choosing a feature set": "🎛️",
    "How this relates to other tabs": "🔗",
    # History — Ukrainian
    "Що це": "📖",
    "Таблиця та перегляд": "🧾",
    "Пошук і фільтри": "🔎",
    "Експорт і аналіз": "📤",
    "Теги": "🏷️",
    "Додаткові дії": "✨",
    "Зв’язок з іншими частинами": "🔗",
    "Якщо чогось не видно": "👀",
    "Навчання з історії": "🎓",
    # History — English
    "What it is": "📖",
    "Table and preview": "🧾",
    "Search and filters": "🔎",
    "Export and analysis": "📤",
    "Tags": "🏷️",
    "Extra actions": "✨",
    "Links to other parts": "🔗",
    "If something is missing": "👀",
    "Learning from history": "🎓",
    # Quiz questions — Ukrainian
    "Типи питань": "❓",
    "Покриття": "📊",
    "Зв’язок з Навчанням": "🔗",
    # Quiz questions — English
    "Question types": "❓",
    "Coverage": "📊",
    "How it relates to Learning": "🔗",
    # Learning — Ukrainian
    "Вкладки": "📑",
    "Типовий flow": "🔄",
    "Створити колоду — деталі": "🃏",
    "Повторення і медіа": "🔁",
    "Статистика": "📊",
    # Learning — English
    "Tabs": "📑",
    "Typical flow": "🔄",
    "Create deck — details": "🃏",
    "Review and media": "🔁",
    "Statistics": "📊",
    # Sync — Ukrainian
    "Навіщо це": "☁️",
    "Що синхронізується": "✅",
    "Що НЕ синхронізується": "🚫",
    "Де налаштувати": "⚙️",
    "Доступні транспорти": "🚚",
    # Sync — English
    "Why sync": "☁️",
    "What is synced": "✅",
    "What is NOT synced": "🚫",
    "Where to configure": "⚙️",
    "Available transports": "🚚",
    # Google Drive — Ukrainian
    "Одноразове налаштування в Google Cloud": "☁️",
    "Підключення в QuickLingo": "🔌",
    "Запуск синхронізації": "▶️",
    "Другий комп’ютер": "💻",
    "Де лежать файли": "📁",
    "Типові проблеми": "🩹",
    # Google Drive — English
    "What it does": "☁️",
    "One-time setup in Google Cloud": "☁️",
    "Connect in QuickLingo": "🔌",
    "Run sync": "▶️",
    "Second computer": "💻",
    "Where files are stored": "📁",
    "Troubleshooting": "🩹",
    # Formatters — Ukrainian
    "Що таке форматер": "🎨",
    "Де задається форматер": "📍",
    "Коли застосовується": "⏱️",
    "Вкладка Форматери (Інструменти → Налаштування → Форматери)": "🧩",
    "Режим «Пресет»": "📦",
    "Режим «Власні правила»": "✏️",
    "Перегляд": "👁️",
    "Зв’язок промпту і форматера": "🔗",
    "Типовий процес": "🔄",
    # Formatters — English
    "What a formatter does": "🎨",
    "Where the formatter is set": "📍",
    "When it runs": "⏱️",
    "Formatters tab (Tools → Settings → Formatters)": "🧩",
    "Preset mode": "📦",
    "Custom rules mode": "✏️",
    "Preview": "👁️",
    "Prompt and formatter must match": "🔗",
    # Glossary — Ukrainian
    "Як це потрапляє в запит до моделі": "📨",
    "Як додати терміни": "➕",
    "Коли глосарій застосовується": "⏱️",
    "Навіщо це потрібно": "💡",
    "Важливо знати": "⚠️",
    "Типовий сценарій для серіалів": "🎬",
    # Glossary — English
    "How it reaches the model": "📨",
    "How to add terms": "➕",
    "When the glossary is used": "⏱️",
    "Why it helps": "💡",
    "Important to know": "⚠️",
    "Typical workflow for TV series": "🎬",
    # Dashboard — Ukrainian
    "Верхній рядок — підсумок": "📌",
    "Графік активності (ліворуч)": "📊",
    "Використання моделей (праворуч)": "🥧",
    "Оновлення": "🔄",
    "Якщо графік не видно": "👀",
    # Dashboard — English
    "Top summary row": "📌",
    "Activity chart (left)": "📊",
    "Model usage (right)": "🥧",
    "Refreshing": "🔄",
    "If a chart is missing": "👀",
}

_HELP_DIALOG_STYLE = """
QDialog#helpDialog {
    background: #ffffff;
}
QLabel#helpVersionBadge {
    background-color: #E0F2FE;
    color: #0284C7;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: bold;
    font-size: 12px;
}
QWidget#helpFooter {
    background: #ffffff;
    border-top: 1px solid #F1F5F9;
}
QPushButton#helpCloseBtn {
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 6px 16px;
    min-height: 28px;
}
QPushButton#helpCloseBtn:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
}
QPushButton#helpCloseBtn:pressed {
    background: #f1f5f9;
}
"""

_HELP_BODY_STYLE = """
QTextBrowser {
    border: none;
    outline: none;
    background: #ffffff;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
}
QScrollBar:vertical {
    border: none;
    background: #F1F5F9;
    width: 8px;
    border-radius: 4px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
    background: none;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}
"""

_HTML_CSS = """
body {
    color: #334155;
    font-size: 14px;
    line-height: 1.55;
    margin: 8px 20px 20px 20px;
    font-family: 'Segoe UI', sans-serif;
}
h2 {
    color: #0F172A;
    font-size: 17px;
    font-weight: 700;
    margin-top: 22px;
    margin-bottom: 8px;
}
h3 {
    color: #0F172A;
    font-size: 15px;
    font-weight: 700;
    margin-top: 18px;
    margin-bottom: 6px;
}
p {
    margin: 0 0 10px 0;
}
ul, ol {
    margin: 4px 0 10px 18px;
    padding-left: 8px;
}
li {
    margin-top: 0px;
    margin-bottom: 4px;
    padding: 0px;
    line-height: 1.4;
}
b, strong {
    color: #0F172A;
    font-weight: 700;
}
tt {
    font-family: Consolas, 'Courier New', monospace;
    font-size: 12.5px;
    color: #0F172A;
}
a {
    color: #0078D7;
    text-decoration: none;
}
"""

_BULLET_RE = re.compile(r"^[•\-\*]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_TERM_SEP_RE = re.compile(r"\s+[—–\-]\s+", re.UNICODE)
_MENU_PATH_RE = re.compile(
    r"(?<![>\w/])("
    r"(?:Інструменти|Вчитися|Довідка|Налаштування|Функції|Навчання|"
    r"Tools|Study|Help|Settings|Features|Learning)"
    r"(?:\s*→\s*[A-Za-zА-Яа-яІіЇїЄєҐґ«»\"']"
    r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9 «»\"'/\-]{0,42})+"
    r")(?![<\w])"
)
_DIRECTION_ID_RE = re.compile(
    r"(?<![<\w])([a-z]{2}-[a-z]{2}(?:-[a-z0-9]+)*)(?![\w>])"
)
_LANG_CODE_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яІіЇїЄєҐґ0-9])(en|uk|ua)(?![A-Za-zА-Яа-яІіЇїЄєҐґ0-9-])"
)
_INLINE_CODE_RE = re.compile(
    r"(?<![<\w])("
    r"Enter|Escape|Esc|Tab|Delete|Backspace|"
    r"Ctrl\+[A-Za-z]|Alt\+[A-Za-z]|Shift\+[A-Za-z]|"
    r"hotkey|Hotkey|FSRS|TTS|OAuth|WebDAV|DPAPI|Anki|Temperature|ID"
    r")(?![\w>])"
)


def help_title_key(topic: str) -> str:
    return f"help.{topic}.title"


def help_body_key(topic: str) -> str:
    return f"help.{topic}.body"


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _inline_code_html(escaped_text: str) -> str:
    # Approved chip template: leading/trailing &nbsp; + <tt> for monospace in Qt.
    return (
        '<span style="background-color: #F1F5F9; color: #0F172A;">'
        f"&nbsp;<tt>{escaped_text}</tt>&nbsp;"
        "</span>"
    )


def _wrap_inline_code(escaped_text: str) -> str:
    """Highlight menu paths, IDs, lang codes and UI terms in escaped HTML text."""

    def _code(match: re.Match[str]) -> str:
        return _inline_code_html(match.group(1))

    text = _MENU_PATH_RE.sub(_code, escaped_text)
    text = _DIRECTION_ID_RE.sub(_code, text)
    text = _INLINE_CODE_RE.sub(_code, text)
    # Lang codes only outside tags (avoid matching inside already-wrapped IDs).
    parts: list[str] = []
    last = 0
    for match in re.finditer(r"<[^>]+>", text):
        parts.append(_LANG_CODE_RE.sub(_code, text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_LANG_CODE_RE.sub(_code, text[last:]))
    text = "".join(parts)
    # Keep punctuation glued to the chip (no " </span> .").
    return re.sub(r"</span>\s+([.,;:!?)\]])", r"</span>\1", text)


def _linkify(text: str) -> str:
    escaped = _escape(text)
    with_links = re.sub(
        r"(https?://[^\s<>\"]+)",
        r'<a href="\1">\1</a>',
        escaped,
    )
    parts: list[str] = []
    last = 0
    for match in re.finditer(r"<[^>]+>", with_links):
        parts.append(_wrap_inline_code(with_links[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_wrap_inline_code(with_links[last:]))
    return "".join(parts)


def _format_term_line(text: str) -> str:
    match = _TERM_SEP_RE.search(text)
    if match and match.start() <= 48:
        left = text[: match.start()].strip()
        right = text[match.end() :].strip()
        sep = match.group(0)
        return f"<b>{_wrap_inline_code(_escape(left))}</b>{_escape(sep)}{_linkify(right)}"
    return _linkify(text)


def _is_heading(line: str) -> bool:
    if not line or _BULLET_RE.match(line) or _NUMBERED_RE.match(line):
        return False
    if line.startswith("(") or line.endswith("."):
        return False
    if ": " in line and len(line) > 42:
        return False
    if len(line) > 72:
        return False
    key = line.rstrip(":").strip()
    known = line in _HEADING_EMOJI or key in _HEADING_EMOJI
    # Colon-lines are section titles only when explicitly mapped (avoids sub-leads).
    if line.endswith(":"):
        return known
    if not known and len(line) > 55 and " — " in line:
        return False
    return True


def _heading_html(line: str, *, first: bool) -> str:
    key = line.rstrip(":").strip()
    emoji = _HEADING_EMOJI.get(line) or _HEADING_EMOJI.get(key)
    # Style menu paths / IDs inside headings the same way as body text.
    body = _wrap_inline_code(_escape(line))
    label = f"{emoji} {body}" if emoji else body
    style = ' style="margin-top: 0;"' if first else ""
    return f"<h2{style}>{label}</h2>"


def plain_help_to_html(text: str) -> str:
    """Convert structured plain-text help articles into styled HTML."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    parts: list[str] = []

    paragraph: list[str] = []
    list_kind: str | None = None
    list_items: list[str] = []
    heading_count = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if not paragraph:
            return
        body = " ".join(paragraph)
        parts.append(f"<p>{_linkify(body)}</p>")
        paragraph = []

    def flush_list() -> None:
        nonlocal list_kind, list_items
        if not list_kind or not list_items:
            list_kind = None
            list_items = []
            return
        tag = list_kind
        parts.append(f"<{tag}>")
        parts.extend(list_items)
        parts.append(f"</{tag}>")
        list_kind = None
        list_items = []

    def start_list(kind: str) -> None:
        nonlocal list_kind
        if list_kind and list_kind != kind:
            flush_list()
        list_kind = kind

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            flush_paragraph()
            start_list("ul")
            list_items.append(f"<li>{_format_term_line(bullet.group(1).strip())}</li>")
            continue

        numbered = _NUMBERED_RE.match(line)
        if numbered:
            flush_paragraph()
            start_list("ol")
            list_items.append(f"<li>{_format_term_line(numbered.group(2).strip())}</li>")
            continue

        if _is_heading(line):
            flush_paragraph()
            flush_list()
            heading_count += 1
            parts.append(_heading_html(line, first=heading_count == 1))
            continue

        flush_list()
        paragraph.append(line)

    flush_paragraph()
    flush_list()

    html_body = "".join(parts)
    # Final pass: glue punctuation to inline chips across the whole document.
    html_body = re.sub(r"</span>\s+([.,;:!?)\]])", r"</span>\1", html_body)

    return (
        "<html><head><meta charset='utf-8'>"
        f"<style>{_HTML_CSS}</style></head>"
        f"<body>{html_body}</body></html>"
    )


class HelpDialog(QDialog):
    def __init__(self, topic: str, parent=None) -> None:
        super().__init__(parent)
        if topic not in HELP_TOPICS:
            raise ValueError(f"Unknown help topic: {topic}")
        self._topic = topic
        self.setObjectName("helpDialog")
        self.setStyleSheet(_HELP_DIALOG_STYLE)
        self.resize(720, 580)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(20, 14, 20, 0)
        badge_row.setSpacing(0)
        self._version_badge = QLabel()
        self._version_badge.setObjectName("helpVersionBadge")
        self._version_badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._version_badge.setVisible(False)
        badge_row.addWidget(self._version_badge, 0, Qt.AlignmentFlag.AlignLeft)
        badge_row.addStretch(1)
        root.addLayout(badge_row)

        self._body = QTextBrowser()
        self._body.setObjectName("helpBody")
        self._body.setOpenExternalLinks(True)
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        self._body.setLineWidth(0)
        self._body.setMidLineWidth(0)
        self._body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._body.setStyleSheet(_HELP_BODY_STYLE)
        root.addWidget(self._body, stretch=1)

        footer = QWidget()
        footer.setObjectName("helpFooter")
        footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(20, 12, 20, 12)
        footer_row.setSpacing(0)
        footer_row.addStretch(1)
        self._close_btn = QPushButton()
        self._close_btn.setObjectName("helpCloseBtn")
        self._close_btn.setDefault(True)
        self._close_btn.setAutoDefault(True)
        self._close_btn.clicked.connect(self.accept)
        footer_row.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(footer, stretch=0)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr(help_title_key(self._topic)))
        body = tr(help_body_key(self._topic))
        if self._topic == "about":
            self._version_badge.setText(
                tr("help.about.version_line").format(version=__version__)
            )
            self._version_badge.setVisible(True)
        else:
            self._version_badge.clear()
            self._version_badge.setVisible(False)
        self._body.setHtml(plain_help_to_html(body))
        self._close_btn.setText(tr("common.close"))


def show_help(topic: str, parent=None) -> None:
    HelpDialog(topic, parent).exec()
