"""Command line entry point for forge-tools.

Each sub-command lives in its own module inside :mod:`forge_tools.commands`
and exposes two functions:

* ``register(subparsers)`` -- adds the sub-command and its arguments.
* ``run(args)`` -- executes the sub-command and returns an exit code.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from forge_tools import __version__
from forge_tools.commands import COMMANDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge-tools",
        description="A collection of small command line tools.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(
        title="commands", dest="command", metavar="<command>", required=True
    )
    for command in COMMANDS:
        sub = command.register(subparsers)
        sub.set_defaults(func=command.run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
