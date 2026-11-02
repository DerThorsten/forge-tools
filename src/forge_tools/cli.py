"""Command line entry point for forge-tools.

Each sub-command lives in its own module inside :mod:`forge_tools.commands`
and exposes two functions:

* ``register(subparsers)`` -- adds the sub-command and its arguments.
* ``run(args)`` -- executes the sub-command and returns an exit code.

Logging is configured centrally here (see :mod:`forge_tools.log`); commands
only need ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from forge_tools import __version__
from forge_tools.commands import COMMANDS
from forge_tools.log import add_log_level_argument, setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge-tools",
        description="A collection of small command line tools.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    add_log_level_argument(parser)
    subparsers = parser.add_subparsers(
        title="commands", dest="command", metavar="<command>", required=True
    )
    for command in COMMANDS:
        sub = command.register(subparsers)
        add_log_level_argument(sub, top_level=False)
        sub.set_defaults(func=command.run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)
    return args.func(args)
