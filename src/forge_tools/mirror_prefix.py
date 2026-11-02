"""Mirror a prefix.dev channel into another channel.

Flow:

1. Download ``repodata.json`` of the source and the target channel for every
   requested platform (a missing platform is treated as empty).
2. For every package of the source that is not yet in the target (matched by
   filename per platform), download it, verify its sha256, upload it to the
   target channel (via py-rattler-build) and delete the local file afterwards.

Channels are given by name (``emscripten-forge-4x``) or as a scoped path
(``foo/the-channel``) relative to the server URL.

Python usage::

    from forge_tools.mirror_prefix import find_missing, mirror_prefix

    missing = find_missing("emscripten-forge-4x", "my-mirror")
    result = mirror_prefix("emscripten-forge-4x", "my-mirror", token="...")
    if not result.ok:
        for pkg, exc in result.failed:
            ...
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from rattler_build import upload_package_to_prefix


DEFAULT_SERVER = "https://prefix.dev"
DEFAULT_PLATFORMS = (
    "emscripten-wasm32",
    "emscripten-wasm64",
    "noarch",
    "linux-64",
    "osx-arm64",
)
TOKEN_ENV = "PREFIX_API_KEY"
SOURCE_TOKEN_ENV = "PREFIX_SOURCE_API_KEY"
USER_AGENT = "forge-tools"
CHUNK = 1 << 20
TIMEOUT = 300

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Package:
    platform: str
    filename: str
    sha256: str | None
    size: int | None

    @property
    def name(self) -> str:
        return f"{self.platform}/{self.filename}"


@dataclass
class MirrorResult:
    """Outcome of :func:`mirror_prefix`."""

    missing: list[Package] = field(default_factory=list)
    uploaded: list[Package] = field(default_factory=list)
    failed: list[tuple[Package, BaseException]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


# --------------------------------------------------------------------------- #
# URLs / HTTP helpers
# --------------------------------------------------------------------------- #
def channel_url(server: str, channel: str) -> str:
    channel = channel.strip("/")
    if not channel:
        raise ValueError("channel name must not be empty")
    return f"{server.rstrip('/')}/{channel}"


def _request(url: str, token: str | None = None, **kwargs) -> urllib.request.Request:
    request = urllib.request.Request(url, **kwargs)
    request.add_header("User-Agent", USER_AGENT)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return request


def _with_retries(func, retries: int, what: str):
    """Call ``func`` retrying on network errors and 5xx/429 responses."""
    for attempt in range(retries + 1):
        try:
            return func()
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429 or attempt == retries:
                raise
            err = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == retries:
                raise
            err = exc
        delay = 2**attempt
        logger.warning("retrying %s in %ss: %s", what, delay, err)
        time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


# --------------------------------------------------------------------------- #
# repodata
# --------------------------------------------------------------------------- #
def fetch_repodata(
    base_url: str, platform: str, token: str | None = None, retries: int = 3
) -> dict:
    """Return the repodata of ``platform``; an empty dict if it doesn't exist."""
    url = f"{base_url}/{platform}/repodata.json"
    logger.debug("fetching %s", url)

    def fetch():
        with urllib.request.urlopen(_request(url, token), timeout=TIMEOUT) as resp:
            return json.load(resp)

    try:
        return _with_retries(fetch, retries, url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise


def packages_of(repodata: dict, platform: str) -> list[Package]:
    result = []
    for key in ("packages", "packages.conda"):
        for filename, record in (repodata.get(key) or {}).items():
            result.append(
                Package(platform, filename, record.get("sha256"), record.get("size"))
            )
    return sorted(result, key=lambda p: p.filename)


def missing_packages(
    source: Iterable[Package], target: Iterable[Package]
) -> list[Package]:
    present = {(p.platform, p.filename) for p in target}
    return [p for p in source if (p.platform, p.filename) not in present]


# --------------------------------------------------------------------------- #
# download / upload
# --------------------------------------------------------------------------- #
def download(
    url: str, dest: Path, token: str | None = None, retries: int = 3
) -> tuple[str, int]:
    """Download ``url`` to ``dest``; return ``(sha256, size)``."""

    def fetch():
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(_request(url, token), timeout=TIMEOUT) as resp:
            with open(dest, "wb") as out:
                while chunk := resp.read(CHUNK):
                    digest.update(chunk)
                    size += len(chunk)
                    out.write(chunk)
        return digest.hexdigest(), size

    return _with_retries(fetch, retries, url)


def upload(
    server: str, channel: str, path: Path, token: str, retries: int = 3
) -> str:
    """Upload ``path`` to a prefix.dev channel via py-rattler-build.

    Packages that already exist on the server are skipped (not an error).
    """

    def send():
        upload_package_to_prefix(
            [str(path)],
            server.rstrip("/"),
            channel.strip("/"),
            api_key=token,
            skip_existing=True,
        )
        return "uploaded"

    for attempt in range(retries + 1):
        try:
            return send()
        except Exception as exc:  # noqa: BLE001 - rattler raises various types
            if attempt == retries:
                raise
            delay = 2**attempt
            logger.warning("retrying upload of %s in %ss: %s", path.name, delay, exc)
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def mirror_package(
    pkg: Package,
    *,
    source_url: str,
    server: str,
    target: str,
    workdir: Path,
    token: str,
    source_token: str | None,
    retries: int,
) -> str:
    """Download, verify, upload and delete a single package."""
    platform_dir = workdir / pkg.platform
    platform_dir.mkdir(parents=True, exist_ok=True)
    local = platform_dir / pkg.filename
    url = f"{source_url}/{pkg.platform}/{urllib.parse.quote(pkg.filename)}"
    try:
        logger.debug("downloading %s -> %s", url, local)
        sha256, size = download(url, local, source_token, retries)
        logger.debug("downloaded %s (%d bytes, sha256 %s)", pkg.filename, size, sha256)
        if pkg.sha256 and sha256 != pkg.sha256:
            raise ValueError(f"sha256 mismatch: expected {pkg.sha256}, got {sha256}")
        if pkg.size is not None and size != pkg.size:
            raise ValueError(f"size mismatch: expected {pkg.size}, got {size}")
        logger.debug("uploading %s to %s/%s", local.name, server, target)
        return upload(server, target, local, token, retries)
    finally:
        # After a successful upload (or a failure) the local copy is not needed.
        local.unlink(missing_ok=True)
        logger.debug("removed %s", local)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def resolve_token(token: str | None, env: str) -> str | None:
    """Return ``token`` or, if not given, the value of ``$env``."""
    return token or os.environ.get(env) or None


def find_missing(
    source: str,
    target: str,
    *,
    platforms: Sequence[str] = DEFAULT_PLATFORMS,
    server: str = DEFAULT_SERVER,
    token: str | None = None,
    source_token: str | None = None,
    retries: int = 3,
) -> list[Package]:
    """Packages of ``source`` that are not (yet) in ``target``.

    ``token`` / ``source_token`` default to ``$PREFIX_API_KEY`` /
    ``$PREFIX_SOURCE_API_KEY`` and are only needed for private channels.
    """
    token = resolve_token(token, TOKEN_ENV)
    source_token = resolve_token(source_token, SOURCE_TOKEN_ENV)
    source_url = channel_url(server, source)
    target_url = channel_url(server, target)

    todo: list[Package] = []
    for platform in platforms:
        src = packages_of(
            fetch_repodata(source_url, platform, source_token, retries), platform
        )
        dst = packages_of(
            fetch_repodata(target_url, platform, token, retries), platform
        )
        missing = missing_packages(src, dst)
        logger.info(
            "%-20s source: %6d  target: %6d  missing: %6d",
            platform, len(src), len(dst), len(missing),
        )
        todo.extend(missing)
    return todo


def mirror_prefix(
    source: str,
    target: str,
    *,
    platforms: Sequence[str] = DEFAULT_PLATFORMS,
    server: str = DEFAULT_SERVER,
    token: str | None = None,
    source_token: str | None = None,
    jobs: int = 4,
    retries: int = 3,
    workdir: str | Path | None = None,
    dry_run: bool = False,
) -> MirrorResult:
    """Mirror all packages of ``source`` that are missing in ``target``.

    Failures of individual packages don't abort the run; they are collected in
    :attr:`MirrorResult.failed`. Errors fetching repodata and invalid
    arguments raise.

    With ``dry_run=True`` nothing is downloaded or uploaded and no token is
    required; only :attr:`MirrorResult.missing` is filled.
    """
    if jobs < 1:
        raise ValueError("jobs must be >= 1")
    token = resolve_token(token, TOKEN_ENV)
    source_token = resolve_token(source_token, SOURCE_TOKEN_ENV)
    if not token and not dry_run:
        raise ValueError(f"no API key given for the target (token or ${TOKEN_ENV})")

    result = MirrorResult()
    result.missing = find_missing(
        source,
        target,
        platforms=platforms,
        server=server,
        token=token,
        source_token=source_token,
        retries=retries,
    )
    todo = result.missing
    if dry_run:
        logger.info("%d package(s) would be mirrored", len(todo))
        return result
    if not todo:
        logger.info("nothing to do")
        return result

    source_url = channel_url(server, source)
    with tempfile.TemporaryDirectory(prefix="forge-tools-mirror-prefix-") as tmp:
        work = Path(workdir) if workdir is not None else Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(
                    mirror_package,
                    pkg,
                    source_url=source_url,
                    server=server,
                    target=target,
                    workdir=work,
                    token=token,
                    source_token=source_token,
                    retries=retries,
                ): pkg
                for pkg in todo
            }
            for done, future in enumerate(as_completed(futures), 1):
                pkg = futures[future]
                try:
                    status = future.result()
                except Exception as exc:  # noqa: BLE001 - collect and continue
                    result.failed.append((pkg, exc))
                    logger.error(
                        "[%d/%d] FAILED    %s: %s", done, len(todo), pkg.name, exc
                    )
                else:
                    result.uploaded.append(pkg)
                    logger.info(
                        "[%d/%d] %-9s %s", done, len(todo), status.upper(), pkg.name
                    )

    logger.info(
        "done: %d ok, %d failed", len(result.uploaded), len(result.failed)
    )
    return result
