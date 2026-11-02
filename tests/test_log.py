import logging

import pytest

from forge_tools import log
from forge_tools.cli import build_parser, main


@pytest.fixture(autouse=True)
def no_env_level(monkeypatch):
    monkeypatch.delenv(log.LEVEL_ENV, raising=False)


def _level():
    return logging.getLogger(log.PACKAGE_LOGGER).level


def test_default_level_is_info(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"")
    assert main(["sha256", str(f)]) == 0
    assert _level() == logging.INFO


@pytest.mark.parametrize(
    "argv",
    [
        ["--log-level", "debug", "sha256", "X"],
        ["sha256", "--log-level", "DEBUG", "X"],
    ],
)
def test_log_level_before_or_after_subcommand(argv):
    args = build_parser().parse_args(argv)
    assert args.log_level == "DEBUG"


def test_subcommand_level_does_not_reset_top_level():
    args = build_parser().parse_args(["--log-level", "ERROR", "sha256", "X"])
    assert args.log_level == "ERROR"


def test_level_from_env(monkeypatch):
    monkeypatch.setenv(log.LEVEL_ENV, "warning")
    assert build_parser().parse_args(["sha256", "X"]).log_level == "WARNING"


def test_invalid_level(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--log-level", "LOUD", "sha256", "X"])
    assert exc.value.code == 2
    assert "invalid log level" in capsys.readouterr().err


def test_setup_logging_is_idempotent(capsys):
    log.setup_logging("INFO")
    log.setup_logging("INFO")
    logging.getLogger("forge_tools.test").info("hello")
    assert capsys.readouterr().err.count("hello") == 1


def test_debug_messages_filtered_at_info(capsys):
    log.setup_logging("INFO")
    logging.getLogger("forge_tools.test").debug("hidden")
    assert "hidden" not in capsys.readouterr().err
