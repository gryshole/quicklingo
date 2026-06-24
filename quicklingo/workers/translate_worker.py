import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.prompts import get_prompt
from quicklingo.providers.registry import ModelEntry


class TranslateWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        text: str,
        direction: str,
        model_entry: ModelEntry,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._direction = direction
        self._model_entry = model_entry

    def run(self) -> None:
        try:
            result = asyncio.run(self._translate())
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(result)

    async def _translate(self) -> str:
        prompt = get_prompt(self._direction)
        return await self._model_entry.provider.translate(
            self._text,
            prompt,
            self._model_entry.model_id,
        )
