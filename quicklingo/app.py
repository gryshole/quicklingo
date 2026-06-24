import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from quicklingo.db import history
from quicklingo.paths import app_root
from quicklingo.ui.main_window import MainWindow

load_dotenv(app_root() / ".env")


def run() -> int:
    history.init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("QuickLingo")

    window = MainWindow()
    window.show()

    return app.exec()
