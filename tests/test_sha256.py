import hashlib
import io

import pytest

from forge_tools.cli import main
from forge_tools import sha256 as sha256_cmd
from forge_tools.sha256 import CHUNK, sha256_of

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


@pytest.fixture
def abc_file(tmp_path):
    path = tmp_path / "abc.txt"
    path.write_bytes(b"abc")
    return path


def test_sha256_of_local_file(abc_file):
    assert sha256_of(str(abc_file)) == (ABC_SHA256, 3)


def test_sha256_of_empty_file(tmp_path):
    path = tmp_path / "empty"
    path.write_bytes(b"")
    assert sha256_of(str(path)) == (EMPTY_SHA256, 0)


def test_sha256_of_multi_chunk_file(tmp_path):
    data = bytes(range(256)) * ((2 * CHUNK + 123) // 256 + 1)
    path = tmp_path / "big.bin"
    path.write_bytes(data)
    assert sha256_of(str(path)) == (hashlib.sha256(data).hexdigest(), len(data))


def test_sha256_of_file_url(abc_file):
    # file:// URLs don't exist as paths, so they go through urllib (no network).
    assert sha256_of(abc_file.as_uri()) == (ABC_SHA256, 3)


def test_sha256_of_url_sets_user_agent(monkeypatch):
    seen = {}

    def fake_urlopen(request):
        seen["url"] = request.full_url
        seen["user_agent"] = request.get_header("User-agent")
        return io.BytesIO(b"abc")

    monkeypatch.setattr(sha256_cmd.urllib.request, "urlopen", fake_urlopen)
    assert sha256_of("https://example.invalid/pkg.tar.gz") == (ABC_SHA256, 3)
    assert seen == {
        "url": "https://example.invalid/pkg.tar.gz",
        "user_agent": "forge-tools",
    }


def test_sha256_of_missing_path_raises(tmp_path):
    with pytest.raises(ValueError):
        sha256_of(str(tmp_path / "does-not-exist"))


def test_cli_prints_digest_size_and_source(abc_file, capsys):
    assert main(["sha256", str(abc_file)]) == 0
    out = capsys.readouterr().out
    assert out == f"{ABC_SHA256}  {3:>12}  {abc_file}\n"


def test_cli_multiple_sources(abc_file, tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    assert main(["sha256", str(abc_file), str(empty)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith(ABC_SHA256)
    assert lines[1].startswith(EMPTY_SHA256)
    assert lines[1].endswith(str(empty))


def test_cli_error_continues_and_returns_1(abc_file, tmp_path, capsys):
    missing = tmp_path / "missing"
    assert main(["sha256", str(missing), str(abc_file)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(f"ERROR  {missing}: ")
    assert lines[1].startswith(ABC_SHA256)


def test_cli_requires_source(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["sha256"])
    assert exc.value.code == 2
    assert "required" in capsys.readouterr().err
