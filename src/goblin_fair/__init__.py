"""goblin_fair: temperature contributions of emissions with the FaIR climate model."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("goblin_fair")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.1.0"

__all__ = ["__version__"]
