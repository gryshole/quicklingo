from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from PySide6.QtCore import QThread, QObject

T = TypeVar("T", bound=QThread)


def run_worker(
    owner: QObject,
    worker: T,
    *,
    on_ok: Callable[..., None],
    on_error: Callable[[str], None],
    attr: str = "_worker",
) -> T:
    """Start a worker and wire standard lifecycle on a host object."""
    previous = getattr(owner, attr, None)
    if previous is not None and isinstance(previous, QThread):
        for signal in (getattr(previous, name, None) for name in ("finished", "error", "progress")):
            if signal is not None:
                try:
                    signal.disconnect()
                except RuntimeError:
                    pass
    setattr(owner, attr, worker)
    if hasattr(worker, "finished"):
        worker.finished.connect(on_ok)  # type: ignore[attr-defined]
    if hasattr(worker, "error"):
        worker.error.connect(on_error)  # type: ignore[attr-defined]
    worker.finished.connect(worker.deleteLater)  # type: ignore[attr-defined]
    if hasattr(worker, "error"):
        worker.error.connect(worker.deleteLater)  # type: ignore[attr-defined]
    worker.start()
    return worker
