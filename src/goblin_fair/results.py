"""The object returned by temperature_contribution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_QUANTILES = (0.05, 0.5, 0.95)


@dataclass(frozen=True)
class ContributionResult:
    """Temperature contribution of a set of emissions, for every ensemble member.

    Year Y is global mean surface temperature at the start of year Y (FaIR
    "timebounds"). Temperatures are in kelvin, which for a change is the same
    as degrees Celsius.

    Attributes
    ----------
    years : array of int, shape (n_years,)
    members : array of calibrated ensemble member ids, shape (n_members,)
    background_temperature : array (n_years, n_members), background run, K
    perturbed_temperature : array (n_years, n_members), background + emissions, K
    metadata : dict describing the run (versions, background, units, ...)
    """

    years: np.ndarray
    members: np.ndarray
    background_temperature: np.ndarray
    perturbed_temperature: np.ndarray
    metadata: dict = field(default_factory=dict)

    @property
    def ensemble(self) -> pd.DataFrame:
        """Contribution (perturbed minus background) per year and member, K."""
        return self._frame(self.perturbed_temperature - self.background_temperature)

    def summary(self, quantiles: Sequence[float] = DEFAULT_QUANTILES) -> pd.DataFrame:
        """Quantiles of the contribution across members, K.

        Default columns p5, p50 (median) and p95. The contribution is taken
        member by member first, so each quantile describes the spread of the
        contribution itself.
        """
        return _quantile_frame(self.ensemble, quantiles)

    def background_warming(
        self, quantiles: Sequence[float] = DEFAULT_QUANTILES
    ) -> pd.DataFrame:
        """Background scenario warming relative to each member's 1850-1900 mean, K.

        The 1850-1900 mean uses timebounds 1850..1901 with half weights at both
        ends, which is the mean over those calendar years (FaIR's convention).
        """
        temps = self.background_temperature
        in_base = (self.years >= 1850) & (self.years <= 1901)
        weights = np.ones(in_base.sum())
        weights[[0, -1]] = 0.5
        baseline = np.average(temps[in_base], axis=0, weights=weights)
        return _quantile_frame(self._frame(temps - baseline), quantiles)

    def plot(self, ax=None, color: str = "C0"):
        """Median contribution with the 5-95 % range shaded. Returns the Axes."""
        import matplotlib.pyplot as plt

        if ax is None:
            _, ax = plt.subplots(figsize=(8, 4.5))
        s = self.summary()
        ax.fill_between(
            s.index, s["p5"], s["p95"], color=color, alpha=0.25, lw=0,
            label="5-95 % range",
        )  # fmt: skip
        ax.plot(s.index, s["p50"], color=color, label="median")
        ax.axhline(0, color="0.6", lw=0.8)
        ax.set_xlabel("Year")
        ax.set_ylabel("Temperature contribution (K)")
        background = self.metadata.get("background")
        title = "Temperature contribution"
        ax.set_title(f"{title} vs {background} background" if background else title)
        ax.legend(frameon=False)
        return ax

    def _frame(self, values: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(
            values,
            index=pd.Index(self.years, name="year"),
            columns=pd.Index(self.members, name="member"),
        )


def _quantile_frame(frame: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
    qs = list(quantiles)
    if not qs or any(not 0 <= q <= 1 for q in qs):
        raise ValueError(
            f"quantiles must be a non-empty sequence of values in [0, 1], "
            f"got {quantiles!r}"
        )
    values = np.quantile(frame.to_numpy(), qs, axis=1).T
    return pd.DataFrame(
        values, index=frame.index, columns=[f"p{q * 100:g}" for q in qs]
    )
