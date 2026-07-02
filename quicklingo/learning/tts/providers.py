from __future__ import annotations

from typing import Protocol


class TtsProvider(Protocol):
    def speak(self, text: str, *, lang: str = "en-US") -> None: ...

    def stop(self) -> None: ...

    def is_speaking(self) -> bool: ...
