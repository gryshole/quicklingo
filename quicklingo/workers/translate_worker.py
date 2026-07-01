import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.config.loader import get_profile, get_prompt, resolve_active_profile_id
from quicklingo.db import history
from quicklingo.features import get_feature, is_enabled
from quicklingo.providers.registry import ModelEntry
from quicklingo.translation import glossary


def build_prompt(direction: str, profile_id: str, source_text: str) -> str:
    prompt = get_prompt(direction, profile_id)
    extras: list[str] = []
    if is_enabled("translation.glossary"):
        glossary_block = glossary.format_for_prompt(direction)
        if glossary_block:
            extras.append(glossary_block)
    if is_enabled("translation.context_window"):
        last_n = int(get_feature("translation.context_window").get("last_n", 3))
        recent = history.get_recent_for_context(
            direction,
            limit=last_n,
            exclude_source=source_text,
        )
        if recent:
            lines = []
            for src, tgt in recent:
                lines.append(f"Previous: {src}\nTranslation: {tgt}")
            extras.append(
                "Recent translations for consistency (do not repeat unless relevant):\n"
                + "\n---\n".join(lines)
            )
    if extras:
        return prompt + "\n\n" + "\n\n".join(extras)
    return prompt


class TranslateWorker(QThread):
    finished = Signal(str)
    chunk = Signal(str)
    error = Signal(str)
    cancelled = Signal()

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
        self._cancelled = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def run(self) -> None:
        if self._cancelled:
            self.cancelled.emit()
            return
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            result = self._loop.run_until_complete(self._translate())
        except asyncio.CancelledError:
            self.cancelled.emit()
            return
        except Exception as exc:
            if self._cancelled:
                self.cancelled.emit()
                return
            self.error.emit(str(exc))
            return
        finally:
            self._loop.close()
            self._loop = None
        if self._cancelled or self.isInterruptionRequested():
            self.cancelled.emit()
            return
        self.finished.emit(result)

    async def _translate(self) -> str:
        if self._cancelled:
            raise asyncio.CancelledError()
        prompt = build_prompt(self._direction, self._profile_id, self._text)
        profile = get_profile(self._profile_id)
        temperature = profile.temperature if profile else 0.2
        provider = self._model_entry.provider

        if is_enabled("translation.streaming"):
            parts: list[str] = []
            async for piece in provider.translate_stream(
                self._text,
                prompt,
                self._model_entry.model_id,
                temperature=temperature,
            ):
                if self._cancelled or self.isInterruptionRequested():
                    raise asyncio.CancelledError()
                parts.append(piece)
                self.chunk.emit(piece)
            return "".join(parts).strip()

        return await provider.translate(
            self._text,
            prompt,
            self._model_entry.model_id,
            temperature=temperature,
        )
