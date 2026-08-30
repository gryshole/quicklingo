"""QSS and layout constants for the review session widget."""

PHONETIC_STYLE = "color: #64748b;"
ANSWER_PHONETIC_STYLE = PHONETIC_STYLE
CONTENT_MIN_WIDTH = 600
CONTENT_MAX_WIDTH = 750
IMAGE_SIZE = 240
IMAGE_RADIUS = 12
MAX_WIDGET = 16777215

REVIEW_STYLE = """
ReviewSessionWidget QLabel#reviewMetaLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QPushButton#btnStartReview {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 22px;
    font-size: 14px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton#btnStartReview:hover:enabled {
    background-color: #2563eb;
}
QPushButton#btnStartReview:disabled {
    background-color: #e2e8f0;
    color: #94a3b8;
}
QPushButton#btnModeToggle {
    background-color: #ffffff;
    color: #475569;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 32px;
}
QPushButton#btnModeToggle:checked {
    background-color: #eff6ff;
    border-color: #3b82f6;
    color: #1d4ed8;
    font-weight: 600;
}
QPushButton#btnShowAnswer {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton#btnShowAnswer:hover:enabled {
    background-color: #f8fafc;
    border-color: #94a3b8;
}
QPushButton#btnAgain {
    background-color: #fef2f2;
    color: #dc2626;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnAgain:hover:enabled {
    background-color: #fee2e2;
}
QPushButton#btnHard {
    background-color: #fff7ed;
    color: #ea580c;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnHard:hover:enabled {
    background-color: #ffedd5;
}
QPushButton#btnGood {
    background-color: #f0fdf4;
    color: #16a34a;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnGood:hover:enabled {
    background-color: #dcfce7;
}
QPushButton#btnEasy {
    background-color: #eff6ff;
    color: #2563eb;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnEasy:hover:enabled {
    background-color: #dbeafe;
}
QFrame#reviewCardFrame {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}
QWidget#reviewImageColumn {
    background: transparent;
}
QFrame#reviewImageFrame {
    background: transparent;
    border: none;
}
QLabel#reviewImageLabel {
    background: transparent;
    border: none;
}
QWidget#reviewFrontColumn {
    background: transparent;
}
QPushButton#reviewSpeakerBtn {
    border: none;
    background: transparent;
    font-family: "Segoe UI Emoji", "Segoe UI Symbol", sans-serif;
    font-size: 16px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0px;
}
QPushButton#reviewSpeakerBtn:hover {
    background-color: #F1F5F9;
    border-radius: 14px;
}
QWidget#reviewMainContent {
    background: transparent;
    min-width: 600px;
    max-width: 750px;
}
QWidget#reviewBackSection {
    background: transparent;
}
QWidget#reviewExampleRow {
    background: transparent;
}
QFrame#reviewExampleQuote {
    background: transparent;
    border: none;
    border-left: 4px solid #CBD5E1;
}
QLabel#reviewDefinitionLabel {
    background: transparent;
}
QLabel#reviewHintLabel {
    color: #64748b;
    background: transparent;
}
QLabel#reviewTermLabel {
    color: #1e293b;
    background: transparent;
}
QLabel#reviewAnswerLabel {
    color: #1d4ed8;
    background: transparent;
}
ReviewSessionWidget QProgressBar#reviewProgressBar {
    border: none;
    background-color: #e2e8f0;
    border-radius: 3px;
    max-height: 4px;
    min-height: 4px;
}
ReviewSessionWidget QProgressBar#reviewProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 3px;
}
QProgressBar {
    border: none;
    background-color: #e2e8f0;
    border-radius: 4px;
    max-height: 6px;
    min-height: 6px;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}
"""
