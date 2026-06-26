import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.config.loader import get_profile, get_prompt, resolve_active_profile_id
from quicklingo.providers.registry import ModelEntry


class TranslateWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        text: str,
        direction: str,
        model_entry: ModelEntry,
        profile_id: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._direction = direction
        self._model_entry = model_entry
        self._profile_id = profile_id or resolve_active_profile_id(direction)

    def run(self) -> None:
        try:
            result = asyncio.run(self._translate())
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(result)

    async def _translate(self) -> str:
        prompt = get_prompt(self._direction, self._profile_id)
        profile = get_profile(self._profile_id)
        temperature = profile.temperature if profile else 0.2
        return await self._model_entry.provider.translate(
            self._text,
            prompt,
            self._model_entry.model_id,
            temperature=temperature,
        )
