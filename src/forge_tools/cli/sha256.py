"""CLI for :mod:`forge_tools.sha256`."""

from __future__ import annotations

import argparse

from forge_tools.sha256 import sha256_of


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("sha256", help="sha256 of URLs or files")
    parser.add_argument("sources", nargs="+", help="URLs or paths")
    return parser


def run(args: argparse.Namespace) -> int:
    status = 0
    for source in args.sources:
        try:
            digest, size = sha256_of(source)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"ERROR  {source}: {exc}")
            status = 1
            continue
        print(f"{digest}  {size:>12}  {source}")
    return status
