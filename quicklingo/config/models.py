from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Direction:
    id: str
    label: str
    source_lang: str
    target_lang: str
    default_profile: str
    enabled: bool = True


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    description: str
    prompts: dict[str, str]
    formatters: dict[str, str]
    temperature: float = 0.2
    prompt_paths: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FormatterDef:
    id: str
    name: str
    engine: str
    rules: list[dict] = field(default_factory=list)
