import subprocess
import sys

import pytest

from forge_tools import __version__
from forge_tools.cli import main


def test_requires_command(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "required" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_command(capsys):
    with pytest.raises(SystemExit):
        main(["does-not-exist"])
    assert "invalid choice" in capsys.readouterr().err

