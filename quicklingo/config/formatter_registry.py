from __future__ import annotations

from collections.abc import Callable

from quicklingo.config.rules_engine import run_rules_v1
from quicklingo.ui.format_output import (
    format_en_ua_output,
    format_plain_output,
    format_ua_en_output,
)

FormatterFn = Callable[[str], str]

_BUILTIN: dict[str, FormatterFn] = {
    "builtin:ua_en_cards": format_ua_en_output,
    "builtin:en_ua_cards": format_en_ua_output,
    "builtin:plain": format_plain_output,
}


def get_formatter_callable(engine: str, rules: list | None = None) -> FormatterFn:
    if engine.startswith("rules:v1"):
        rule_list = rules or []

        def _run(text: str) -> str:
            return run_rules_v1(rule_list, text)

        return _run
    fn = _BUILTIN.get(engine)
    if fn is None:
        raise KeyError(f"Unknown formatter engine: {engine}")
    return fn
