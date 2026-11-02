"""``sha256``: sha256 and size of URLs or local files (for recipe sources)."""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

CHUNK = 1 << 20


def sha256_of(source: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    if Path(source).exists():
        stream = open(source, "rb")
    else:
        request = urllib.request.Request(source, headers={"User-Agent": "forge-tools"})
        stream = urllib.request.urlopen(request)
    with stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


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
