import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from forge_tools.cli import main
from forge_tools.commands import mirror_prefix as mirror
from forge_tools.commands.mirror_prefix import (
    Package,
    channel_url,
    missing_packages,
    packages_of,
)


def _pkg(data: bytes) -> dict:
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


class FakePrefix:
    """Minimal stand-in for prefix.dev: repodata, downloads and uploads."""

    def __init__(self):
        # channel -> platform -> filename -> bytes
        self.channels: dict[str, dict[str, dict[str, bytes]]] = {}
        self.uploads: list[dict] = []
        self.fail_upload: set[str] = set()
        self.corrupt: set[str] = set()

    def add(self, channel, platform, filename, data):
        self.channels.setdefault(channel, {}).setdefault(platform, {})[filename] = data

    def repodata(self, channel, platform):
        files = self.channels.get(channel, {}).get(platform)
        if files is None:
            return None
        rd = {"info": {"subdir": platform}, "packages": {}, "packages.conda": {}}
        for name, data in files.items():
            key = "packages.conda" if name.endswith(".conda") else "packages"
            rd[key][name] = _pkg(data)
        return rd


@pytest.fixture
def server(monkeypatch):
    fake = FakePrefix()

    def fake_upload(package_files, url, channels, *, api_key=None, **kwargs):
        for path in package_files:
            name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            with open(path, "rb") as f:
                body = f.read()
            fake.uploads.append(
                {
                    "channel": channels,
                    "name": name,
                    "auth": f"Bearer {api_key}",
                    "body": body,
                    "skip_existing": kwargs.get("skip_existing"),
                }
            )
            if name in fake.fail_upload:
                raise RuntimeError("upload failed")

    monkeypatch.setattr(mirror, "upload_package_to_prefix", fake_upload)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body=b""):
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            channel, platform, filename = self.path.strip("/").rsplit("/", 2)
            if filename == "repodata.json":
                rd = fake.repodata(channel, platform)
                if rd is None:
                    return self._send(404, b"File could not be found")
                return self._send(200, json.dumps(rd).encode())
            data = fake.channels.get(channel, {}).get(platform, {}).get(filename)
            if data is None:
                return self._send(404)
            if filename in fake.corrupt:
                data = b"garbage"
            self._send(200, data)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield fake
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(autouse=True)
def no_env_token(monkeypatch):
    monkeypatch.delenv(mirror.TOKEN_ENV, raising=False)
    monkeypatch.delenv(mirror.SOURCE_TOKEN_ENV, raising=False)


def run_mirror(server, *extra):
    return main(
        ["mirror-prefix", "src", "org/dst", "--server", server.url, "--retries", "0", *extra]
    )


# --------------------------------------------------------------------------- #
# unit tests
# --------------------------------------------------------------------------- #
def test_channel_urls():
    assert channel_url("https://prefix.dev/", "emscripten-forge-4x") == (
        "https://prefix.dev/emscripten-forge-4x"
    )
    assert channel_url("https://prefix.dev", "/foo/bar/") == "https://prefix.dev/foo/bar"
    with pytest.raises(ValueError):
        channel_url("https://prefix.dev", "/")


def test_packages_of_reads_both_formats():
    rd = {
        "packages": {"b-1-0.tar.bz2": {"sha256": "x", "size": 1}},
        "packages.conda": {"a-1-0.conda": {"sha256": "y", "size": 2}},
    }
    assert packages_of(rd, "noarch") == [
        Package("noarch", "a-1-0.conda", "y", 2),
        Package("noarch", "b-1-0.tar.bz2", "x", 1),
    ]
    assert packages_of({}, "noarch") == []


def test_missing_packages_is_per_platform():
    src = [Package("noarch", "a.conda", None, None), Package("linux-64", "a.conda", None, None)]
    dst = [Package("noarch", "a.conda", None, None)]
    assert missing_packages(src, dst) == [Package("linux-64", "a.conda", None, None)]


# --------------------------------------------------------------------------- #
# end-to-end against the fake server
# --------------------------------------------------------------------------- #
def test_mirror_uploads_only_missing(server, tmp_path, capsys):
    server.add("src", "noarch", "a-1-0.tar.bz2", b"aaa")
    server.add("src", "noarch", "b-1-0.conda", b"bbb")
    server.add("src", "emscripten-wasm32", "c-1-0.tar.bz2", b"ccc")
    server.add("org/dst", "noarch", "a-1-0.tar.bz2", b"aaa")
    workdir = tmp_path / "work"

    rc = run_mirror(
        server, "-p", "noarch", "-p", "emscripten-wasm32", "--token", "T",
        "--workdir", str(workdir),
    )

    assert rc == 0
    uploaded = sorted(u["name"] for u in server.uploads)
    assert uploaded == ["b-1-0.conda", "c-1-0.tar.bz2"]
    for u in server.uploads:
        assert u["channel"] == "org/dst"
        assert u["auth"] == "Bearer T"
    # downloaded files are removed after upload
    assert [p for p in workdir.rglob("*") if p.is_file()] == []
    out = capsys.readouterr().err
    assert "done: 2 ok, 0 failed" in out


def test_mirror_missing_platform_is_empty(server, capsys):
    server.add("src", "noarch", "a-1-0.conda", b"aaa")
    rc = run_mirror(server, "--token", "T")  # all default platforms
    assert rc == 0
    assert [u["name"] for u in server.uploads] == ["a-1-0.conda"]


def test_mirror_dry_run_uploads_nothing(server, capsys):
    server.add("src", "noarch", "a-1-0.conda", b"aaa")
    rc = run_mirror(server, "-p", "noarch", "--dry-run")
    assert rc == 0
    assert server.uploads == []
    captured = capsys.readouterr()
    assert captured.out == "noarch/a-1-0.conda\n"
    assert "1 package(s) would be mirrored" in captured.err


def test_mirror_nothing_to_do(server, capsys):
    server.add("src", "noarch", "a-1-0.conda", b"aaa")
    server.add("org/dst", "noarch", "a-1-0.conda", b"aaa")
    assert run_mirror(server, "-p", "noarch", "--token", "T") == 0
    assert server.uploads == []
    assert "nothing to do" in capsys.readouterr().err


def test_mirror_token_from_env(server, monkeypatch):
    monkeypatch.setenv(mirror.TOKEN_ENV, "ENVTOKEN")
    server.add("src", "noarch", "a-1-0.conda", b"aaa")
    assert run_mirror(server, "-p", "noarch") == 0
    assert server.uploads[0]["auth"] == "Bearer ENVTOKEN"


def test_mirror_requires_token(server, capsys):
    assert run_mirror(server, "-p", "noarch") == 2
    assert mirror.TOKEN_ENV in capsys.readouterr().err


def test_mirror_sha_mismatch_is_not_uploaded(server, tmp_path, capsys):
    server.add("src", "noarch", "a-1-0.conda", b"aaa")
    server.add("src", "noarch", "b-1-0.conda", b"bbb")
    server.corrupt.add("a-1-0.conda")
    workdir = tmp_path / "work"
    rc = run_mirror(server, "-p", "noarch", "--token", "T", "--workdir", str(workdir))
    assert rc == 1
    assert [u["name"] for u in server.uploads] == ["b-1-0.conda"]
    out = capsys.readouterr().err
    assert "FAILED    noarch/a-1-0.conda: sha256 mismatch" in out
    assert "done: 1 ok, 1 failed" in out
    assert [p for p in workdir.rglob("*") if p.is_file()] == []


def test_mirror_upload_error_continues(server, capsys):
    server.add("src", "noarch", "a-1-0.conda", b"aaa")
    server.add("src", "noarch", "b-1-0.conda", b"bbb")
    server.fail_upload.add("a-1-0.conda")
    rc = run_mirror(server, "-p", "noarch", "--token", "T", "-j", "1")
    assert rc == 1
    out = capsys.readouterr().err
    assert "FAILED    noarch/a-1-0.conda" in out
    assert "UPLOADED  noarch/b-1-0.conda" in out
