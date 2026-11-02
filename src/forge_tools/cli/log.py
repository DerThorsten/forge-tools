"""CLI side of logging: the ``--log-level`` option.

The option is added centrally by :func:`forge_tools.cli.build_parser` to the
top-level parser and to every sub-command parser, so it is accepted before or
after the sub-command name. Without the option the level comes from
``$FORGE_TOOLS_LOG_LEVEL``, falling back to ``INFO``. The chosen level is
applied via :func:`forge_tools.log.setup_logging` in :func:`forge_tools.cli.main`.
"""

from __future__ import annotations

import argparse
import os

from forge_tools.log import DEFAULT_LEVEL, LEVELS

LEVEL_ENV = "FORGE_TOOLS_LOG_LEVEL"


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
        # A string default is passed through ``type`` by argparse at parse
        # time, so an invalid $FORGE_TOOLS_LOG_LEVEL gives a usage error.
        default = os.environ.get(LEVEL_ENV, DEFAULT_LEVEL)
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
