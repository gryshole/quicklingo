from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import NoReturn

import httpx

from quicklingo.i18n import tr
from quicklingo.i18n.translator import TranslatableError


def format_api_error(response: httpx.Response) -> str:
    """Extract a short human-readable error message from an API error response."""
    try:
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message[:300]
    except (json.JSONDecodeError, TypeError):
        pass
    return (response.text.strip() or response.reason_phrase or "")[:300]


@dataclass(frozen=True)
class ParsedApiError:
    message: str
    code: str
    limit_kind: str | None
    retry_seconds: int | None


def parse_openai_compat_error(body: str) -> ParsedApiError:
    message = body.strip()
    code = ""
    try:
        data = json.loads(body)
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict):
            msg = error.get("message")
            if isinstance(msg, str) and msg.strip():
                message = msg.strip()
            code_val = error.get("code")
            if isinstance(code_val, str):
                code = code_val
    except (json.JSONDecodeError, TypeError):
        pass

    return ParsedApiError(
        message=message,
        code=code,
        limit_kind=_detect_limit_kind(message),
        retry_seconds=_extract_retry_seconds(message),
    )


def _detect_limit_kind(message: str) -> str | None:
    lower = message.lower()
    if "requests per minute" in lower or "(rpm)" in lower:
        return "rpm"
    if "tokens per minute" in lower or "(tpm)" in lower:
        return "tpm"
    if "requests per day" in lower or "(rpd)" in lower:
        return "rpd"
    if "tokens per day" in lower or "(tpd)" in lower:
        return "tpd"
    return None


def _extract_retry_seconds(message: str) -> int | None:
    match = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", message, re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))))
    return None


def _retry_hint(retry_seconds: int | None) -> str:
    if retry_seconds is not None:
        return tr("errors.api_retry_in_seconds", seconds=retry_seconds)
    return tr("errors.api_retry_soon")


def _short_message(parsed: ParsedApiError, *, status_code: int) -> str:
    if parsed.message:
        return parsed.message[:300]
    return str(status_code)


def raise_openai_compat_api_error(*, status_code: int, body: str) -> NoReturn:
    parsed = parse_openai_compat_error(body)
    raw_detail = body.strip() or str(status_code)
    retry_hint = _retry_hint(parsed.retry_seconds)

    if status_code == 429 or parsed.code == "rate_limit_exceeded":
        if parsed.limit_kind == "rpm":
            raise TranslatableError(
                "errors.api_rate_limit_rpm",
                retry_hint=retry_hint,
                raw_detail=raw_detail,
            )
        if parsed.limit_kind == "tpm":
            raise TranslatableError(
                "errors.api_rate_limit_tpm",
                retry_hint=retry_hint,
                raw_detail=raw_detail,
            )
        raise TranslatableError(
            "errors.api_rate_limit",
            retry_hint=retry_hint,
            raw_detail=raw_detail,
        )

    raise TranslatableError(
        "errors.api_error_short",
        status=status_code,
        message=_short_message(parsed, status_code=status_code),
        raw_detail=raw_detail,
    )

