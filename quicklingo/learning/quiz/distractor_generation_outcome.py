from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DistractorGenerationOutcome:
    created: int
    cancelled: bool
    rate_limited: bool
    total_attempted: int
    retry_seconds: int | None = None
