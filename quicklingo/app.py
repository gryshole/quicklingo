import sys

from PySide6.QtWidgets import QApplication

from quicklingo.app_icon import configure_windows_app_id, load_app_icon
from quicklingo.db import history
from quicklingo.i18n import init_language, language_changed
from quicklingo.ui.main_window import MainWindow


def run() -> int:
    configure_windows_app_id()
    history.init_db()
    init_language()

    app = QApplication(sys.argv)
    app.setApplicationName("QuickLingo")
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    language_changed().connect(window.retranslate_ui)
    window.show()

    return app.exec()