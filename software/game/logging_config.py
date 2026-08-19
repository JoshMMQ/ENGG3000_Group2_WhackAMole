"""Rotating diagnostics for game crashes and tracking investigations."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


DEFAULT_LOG_PATH = Path("runtime-logs/game.log")
MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_LOG_COUNT = 3
_MANAGED_HANDLER_ATTRIBUTE = "_whackamole_managed_handler"


def configure_logging(log_path: str | Path = DEFAULT_LOG_PATH) -> Path:
    """Configure detailed rotating file logs plus warning output on stderr."""

    path = Path(log_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in tuple(root_logger.handlers):
        if getattr(handler, _MANAGED_HANDLER_ATTRIBUTE, False):
            root_logger.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_LOG_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    setattr(file_handler, _MANAGED_HANDLER_ATTRIBUTE, True)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    setattr(console_handler, _MANAGED_HANDLER_ATTRIBUTE, True)
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info("Logging initialized path=%s", path.resolve())
    return path
