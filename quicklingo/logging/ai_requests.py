from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

from quicklingo.paths import user_data_dir

_LOG_DIR = user_data_dir() / "logs"
_LOG_FILE = _LOG_DIR / "ai_requests.log"
_MAX_FIELD_CHARS = 4000

_logger: logging.Logger | None = None
_purpose: ContextVar[str] = ContextVar("ai_request_purpose", default="unknown")


def log_file_path() -> Path:
    return _LOG_FILE


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("quicklingo.ai_requests")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

    handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    _logger = logger
    return logger


def current_purpose() -> str:
    return _purpose.get()


@contextmanager
def ai_request_scope(purpose: str):
    token = _purpose.set(purpose)
    try:
        yield
    finally:
        _purpose.reset(token)


def truncate_text(text: str, *, max_chars: int = _MAX_FIELD_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... [{len(text)} chars total]"


def log_request_start(
    *,
    provider_id: str,
    model: str,
    method: str,
    purpose: str,
    stream: bool,
    temperature: float,
    system_chars: int,
    user_chars: int,
) -> None:
    get_logger().info(
        "START provider=%s model=%s method=%s purpose=%s stream=%s "
        "temperature=%.2f system_chars=%d user_chars=%d",
        provider_id,
        model,
        method,
        purpose,
        stream,
        temperature,
        system_chars,
        user_chars,
    )


def log_request_prompts(*, system_text: str, user_text: str) -> None:
    logger = get_logger()
    if system_text:
        logger.debug("system_prompt=%s", truncate_text(system_text))
    if user_text:
        logger.debug("user_prompt=%s", truncate_text(user_text))


def log_request_success(
    *,
    provider_id: str,
    model: str,
    method: str,
    purpose: str,
    stream: bool,
    duration_ms: float,
    response_chars: int,
    response_text: str,
) -> None:
    logger = get_logger()
    logger.info(
        "OK provider=%s model=%s method=%s purpose=%s stream=%s "
        "duration_ms=%.1f response_chars=%d",
        provider_id,
        model,
        method,
        purpose,
        stream,
        duration_ms,
        response_chars,
    )
    if response_text:
        logger.debug("response=%s", truncate_text(response_text))
    if not response_text.strip():
        logger.warning(
            "EMPTY_RESPONSE provider=%s model=%s method=%s purpose=%s",
            provider_id,
            model,
            method,
            purpose,
        )


def log_request_cancelled(
    *,
    provider_id: str,
    model: str,
    method: str,
    purpose: str,
    duration_ms: float,
) -> None:
    get_logger().warning(
        "CANCELLED provider=%s model=%s method=%s purpose=%s duration_ms=%.1f",
        provider_id,
        model,
        method,
        purpose,
        duration_ms,
    )


def log_request_error(
    *,
    provider_id: str,
    model: str,
    method: str,
    purpose: str,
    duration_ms: float,
    exc: BaseException,
) -> None:
    from quicklingo.i18n.translator import TranslatableError

    logger = get_logger()
    logger.error(
        "FAIL provider=%s model=%s method=%s purpose=%s duration_ms=%.1f "
        "error_type=%s error=%s",
        provider_id,
        model,
        method,
        purpose,
        duration_ms,
        type(exc).__name__,
        exc,
    )
    if isinstance(exc, TranslatableError) and exc.raw_detail:
        logger.debug("raw_error=%s", truncate_text(exc.raw_detail))


def log_validation_retry(*, purpose: str, detail: str) -> None:
    get_logger().warning("RETRY purpose=%s detail=%s", purpose, detail)
