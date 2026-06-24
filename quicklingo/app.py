import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from quicklingo.app_icon import configure_windows_app_id, load_app_icon
from quicklingo.db import history
from quicklingo.paths import app_root
from quicklingo.ui.main_window import MainWindow

load_dotenv(app_root() / ".env")


def run() -> int:
    configure_windows_app_id()
    history.init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("QuickLingo")
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()

    return app.exec()