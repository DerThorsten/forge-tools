"""CLI for :mod:`forge_tools.mirror_prefix`."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from forge_tools import mirror_prefix as impl

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "mirror-prefix",
        help="mirror a prefix.dev channel to another channel",
        description=impl.__doc__.split("Python usage::")[0].rstrip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", help="source channel, e.g. emscripten-forge-6x")
    parser.add_argument("target", help="target channel, e.g. emscripten-forge/6x")
    parser.add_argument(
        "-p",
        "--platform",
        dest="platforms",
        action="append",
        metavar="PLATFORM",
        help=(
            "platform to mirror (repeatable); default: "
            + " ".join(impl.DEFAULT_PLATFORMS)
        ),
    )
    parser.add_argument(
        "--server",
        default=impl.DEFAULT_SERVER,
        help=f"default: {impl.DEFAULT_SERVER}",
    )
    parser.add_argument(
        "--token",
        default=None,
        help=f"API key for the target channel (default: ${impl.TOKEN_ENV})",
    )
    parser.add_argument(
        "--source-token",
        default=None,
        help=(
            "API key for a private source channel "
            f"(default: ${impl.SOURCE_TOKEN_ENV})"
        ),
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=4, help="parallel transfers (default: 4)"
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="retries per request (default: 3)"
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="directory for temporary downloads (default: a fresh temp dir)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="only list the packages that would be mirrored",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    try:
        result = impl.mirror_prefix(
            args.source,
            args.target,
            platforms=args.platforms or impl.DEFAULT_PLATFORMS,
            server=args.server,
            token=args.token,
            source_token=args.source_token,
            jobs=args.jobs,
            retries=args.retries,
            workdir=args.workdir,
            dry_run=args.dry_run,
        )
    except ValueError as exc:  # invalid arguments / missing token
        logger.error("%s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001 - e.g. repodata could not be fetched
        logger.error("%s", exc)
        return 1

    if args.dry_run:
        for pkg in result.missing:
            print(pkg.name)  # result -> stdout
    return 0 if result.ok else 1
