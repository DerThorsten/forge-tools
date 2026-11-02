"""Central logging setup for forge-tools.

Sub-commands don't configure logging themselves; they just use

    logger = logging.getLogger(__name__)

and :func:`forge_tools.cli.main` calls :func:`setup_logging` with the level
from ``--log-level`` (accepted before or after the sub-command name) or the
``FORGE_TOOLS_LOG_LEVEL`` environment variable.

Log messages go to stderr; a command's actual results (e.g. a list of
checksums) are printed to stdout so they can be piped.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DEFAULT_LEVEL = "INFO"
LEVEL_ENV = "FORGE_TOOLS_LOG_LEVEL"
PACKAGE_LOGGER = "forge_tools"

_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
_DEBUG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(threadName)s]: %(message)s"
_DATEFMT = "%H:%M:%S"


def _level(value: str) -> str:
    level = value.strip().upper()
    if level not in LEVELS:
        raise argparse.ArgumentTypeError(
            f"invalid log level {value!r} (choose from {', '.join(LEVELS)})"
        )
    return level


def add_log_level_argument(
    parser: argparse.ArgumentParser, *, top_level: bool = True
) -> None:
    """Add ``--log-level`` to ``parser``.

    On sub-parsers (``top_level=False``) the default is suppressed so that a
    value given before the sub-command is not overwritten.
    """
    if top_level:
        default = _level(os.environ.get(LEVEL_ENV, DEFAULT_LEVEL))
    else:
        default = argparse.SUPPRESS
    parser.add_argument(
        "--log-level",
        type=_level,
        default=default,
        metavar="LEVEL",
        help=(
            f"logging verbosity: {', '.join(LEVELS)} "
            f"(default: ${LEVEL_ENV} or {DEFAULT_LEVEL})"
        ),
    )


def setup_logging(level: str = DEFAULT_LEVEL) -> logging.Logger:
    """Configure the ``forge_tools`` package logger to log to stderr.

    Safe to call repeatedly (e.g. from tests): previously installed
    forge-tools handlers are replaced, not duplicated.
    """
    logger = logging.getLogger(PACKAGE_LOGGER)
    for handler in list(logger.handlers):
        if getattr(handler, "_forge_tools", False):
            logger.removeHandler(handler)
            handler.close()

    numeric = logging.getLevelName(level)
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
