"""sha256 and size of URLs or local files (e.g. for recipe sources)."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

CHUNK = 1 << 20
USER_AGENT = "forge-tools"


def sha256_of(source: str) -> tuple[str, int]:
    """Return ``(sha256 hexdigest, size in bytes)`` of a local path or URL."""
    digest = hashlib.sha256()
    size = 0
    if Path(source).exists():
        stream = open(source, "rb")
    else:
        request = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
        stream = urllib.request.urlopen(request)
    with stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size
