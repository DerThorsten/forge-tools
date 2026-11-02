"""forge-tools: a collection of small command line tools."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("forge-tools")
except PackageNotFoundError:  # pragma: no cover - package not installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
