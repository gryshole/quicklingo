from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout

from quicklingo.i18n import tr
from quicklingo.ui.widgets.quiz_questions_browser import QuizQuestionsBrowserWidget
from quicklingo.ui.window_state import restore_window_geometry, save_window_geometry


class QuizQuestionsWindow(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        restore_window_geometry(self, "quiz_questions", default_width=1015, default_height=850)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._browser = QuizQuestionsBrowserWidget()
        layout.addWidget(self._browser, stretch=1)

        self.retranslate_ui()
        self._browser.reload_decks()

    def refresh(self) -> None:
        self._browser.reload_decks()
        self._browser.refresh()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("main.menu_quiz_questions"))
        self._browser.retranslate_ui()

    def closeEvent(self, event: QCloseEvent) -> None:
        save_window_geometry(self, "quiz_questions")
        super().closeEvent(event)
