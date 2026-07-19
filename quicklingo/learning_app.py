from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

import quicklingo.app as ql_app
import quicklingo.qt_env  # noqa: F401 — before QtMultimedia
from quicklingo.app_icon import configure_windows_app_id, load_app_icon
from quicklingo.db import history
from quicklingo.features import feature_changed
from quicklingo.i18n import init_language, language_changed, tr
from quicklingo.qt_env import apply_qt_logging_filters
from quicklingo.ui.app_theme import disable_combo_popup_animation
from quicklingo.ui.learning_window import LearningWindow

_LEARNING_APP_ID = "gryshole.quicklingo.learning.1"


class QuickLingoLearningApp:
    def __init__(self, qt_app: QApplication, window: LearningWindow) -> None:
        self._app = qt_app
        self._window = window

    def prepare_quit_for_update(self) -> None:
        """No extra cleanup; UpdateController quits after launching the updater."""
        pass


def run() -> int:
    configure_windows_app_id(_LEARNING_APP_ID)
    history.init_db()
    init_language()

    app = QApplication(sys.argv)
    apply_qt_logging_filters()
    disable_combo_popup_animation(app)
    app.setApplicationName("QuickLingo Learning")
    app.setApplicationDisplayName(tr("learning.app_title"))
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    window = LearningWindow(standalone=True)
    if icon is not None:
        window.setWindowIcon(icon)

    language_changed().connect(window.retranslate_ui)
    feature_changed().changed.connect(lambda _: window.retranslate_ui())

    ql_app._app = QuickLingoLearningApp(app, window)
    window.show()
    return app.exec()
