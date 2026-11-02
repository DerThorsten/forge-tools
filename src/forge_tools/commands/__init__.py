"""Registry of all forge-tools sub-commands."""

from forge_tools.commands import (
    mirror_prefix,
    sha256,
)

COMMANDS = [
    mirror_prefix,
    sha256,
]

__all__ = ["COMMANDS"]
