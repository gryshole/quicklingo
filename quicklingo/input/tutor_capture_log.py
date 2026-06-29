from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from quicklingo.paths import user_data_dir

_LOG_DIR = user_data_dir() / "logs"
_LOG_FILE = _LOG_DIR / "tutor_capture.log"

_logger: logging.Logger | None = None


def log_file_path() -> Path:
    return _LOG_FILE


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("quicklingo.tutor_capture")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

    handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    _logger = logger
    return logger


def log_debug(message: str) -> None:
    get_logger().debug(message)


def log_info(message: str) -> None:
    get_logger().info(message)


def log_warning(message: str) -> None:
    get_logger().warning(message)
