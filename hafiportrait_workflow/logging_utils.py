from __future__ import annotations

import logging
from logging import Logger
from pathlib import Path
import time

from .models import Config

_LOGGER: Logger | None = None


def _normalize_level(level: str) -> int:
    name = (level or "INFO").strip().upper()
    return getattr(logging, name, logging.INFO)


def get_logger(cfg: Config) -> Logger:
    """Get a configured workflow logger (console + daily file).

    This is configured once per process to avoid duplicate handlers.
    """

    global _LOGGER
    if _LOGGER is not None:
        # Keep level in sync with config.
        _LOGGER.setLevel(_normalize_level(cfg.log_level))
        return _LOGGER

    cfg.logs_path.mkdir(parents=True, exist_ok=True)
    log_file = cfg.logs_path / f"run-{time.strftime('%Y%m%d')}.log"

    logger = logging.getLogger("hafiportrait_workflow")
    logger.setLevel(_normalize_level(cfg.log_level))
    logger.propagate = False

    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(_normalize_level(cfg.log_level))

    # File (append)
    fh = logging.FileHandler(Path(log_file), encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(_normalize_level(cfg.log_level))

    logger.addHandler(sh)
    logger.addHandler(fh)

    _LOGGER = logger
    return logger


def log_debug(cfg: Config, msg: str) -> None:
    get_logger(cfg).debug(msg)


def log_info(cfg: Config, msg: str) -> None:
    get_logger(cfg).info(msg)


def log_warning(cfg: Config, msg: str) -> None:
    get_logger(cfg).warning(msg)


def log_error(cfg: Config, msg: str) -> None:
    get_logger(cfg).error(msg)


def log_line(cfg: Config, msg: str) -> None:
    """Backward-compatible helper (maps to INFO)."""

    log_info(cfg, msg)
