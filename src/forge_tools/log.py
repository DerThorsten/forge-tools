"""Logging setup for forge-tools.

Library modules never configure logging; they only use

    logger = logging.getLogger(__name__)

All of them live below the ``forge_tools`` logger, so a single call to
:func:`setup_logging` enables their output. The CLI does this for you (see
:mod:`forge_tools.cli.log`); from Python call it yourself if you want to see
progress messages::

    from forge_tools.log import setup_logging
    setup_logging("DEBUG")
"""

from __future__ import annotations

import logging
import sys

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DEFAULT_LEVEL = "INFO"
PACKAGE_LOGGER = "forge_tools"

_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
_DEBUG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(threadName)s]: %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level: str | int = DEFAULT_LEVEL) -> logging.Logger:
    """Configure the ``forge_tools`` package logger to log to stderr.

    ``level`` is a level name (case-insensitive, one of :data:`LEVELS`) or a
    numeric :mod:`logging` level. Safe to call repeatedly: a previously
    installed forge-tools handler is replaced, not duplicated.
    """
    if isinstance(level, str):
        name = level.strip().upper()
        if name not in LEVELS:
            raise ValueError(
                f"invalid log level {level!r} (choose from {', '.join(LEVELS)})"
            )
        numeric = logging.getLevelName(name)
    else:
        numeric = int(level)

    logger = logging.getLogger(PACKAGE_LOGGER)
    for handler in list(logger.handlers):
        if getattr(handler, "_forge_tools", False):
            logger.removeHandler(handler)
            handler.close()

    handler = logging.StreamHandler(sys.stderr)
    handler._forge_tools = True  # type: ignore[attr-defined]
    handler.setFormatter(
        logging.Formatter(
            _DEBUG_FORMAT if numeric <= logging.DEBUG else _FORMAT, _DATEFMT
        )
    )
    logger.addHandler(handler)
    logger.setLevel(numeric)
    return logger
