from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
)

from quicklingo.i18n import tr

HELP_TOPICS = (
    "about",
    "models",
    "directions_profiles",
    "formatters",
    "features",
    "history",
    "learning",
    "dashboard",
    "glossary",
)


def help_title_key(topic: str) -> str:
    return f"help.{topic}.title"


def help_body_key(topic: str) -> str:
    return f"help.{topic}.body"


class HelpDialog(QDialog):
    def __init__(self, topic: str, parent=None) -> None:
        super().__init__(parent)
        if topic not in HELP_TOPICS:
            raise ValueError(f"Unknown help topic: {topic}")
        self._topic = topic
        self.resize(680, 560)

        layout = QVBoxLayout(self)
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(True)
        layout.addWidget(self._body, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        self._close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        layout.addWidget(buttons)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr(help_title_key(self._topic)))
        self._body.setPlainText(tr(help_body_key(self._topic)))
        if self._close_btn is not None:
            self._close_btn.setText(tr("common.close"))


def show_help(topic: str, parent=None) -> None:
    HelpDialog(topic, parent).exec()
