"""goblin_fair: temperature contributions of emissions with the FaIR climate model."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("goblin_fair")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.1.0"

from goblin_fair.api import list_backgrounds, temperature_contribution  # noqa: E402
from goblin_fair.results import ContributionResult  # noqa: E402

__all__ = [
    "temperature_contribution",
    "ContributionResult",
    "list_backgrounds",
    "__version__",
]
