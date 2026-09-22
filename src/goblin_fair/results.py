"""The object returned by temperature_contribution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from goblin_fair import neutrality as _neutrality

DEFAULT_QUANTILES = (0.05, 0.5, 0.95)


@dataclass(frozen=True)
class ContributionResult:
    """Temperature contribution of a set of emissions, for every ensemble member.

    The contribution is the world with the emissions minus the world without
    them. With method "leave_one_out" the "with" run is the unmodified SSP
    background; with "add" the "without" run is.

    Year Y is global mean surface temperature at the start of year Y (FaIR
    "timebounds"). Temperatures are in kelvin, which for a change is the same
    as degrees Celsius.

    Attributes
    ----------
    years : array of int, shape (n_years,)
    members : array of calibrated ensemble member ids, shape (n_members,)
    with_temperature : array (n_years, n_members), run with the emissions, K
    without_temperature : array (n_years, n_members), run without them, K
    method : "leave_one_out" or "add"
    metadata : dict describing the run (versions, background, units, ...)
    """

    years: np.ndarray
    members: np.ndarray
    with_temperature: np.ndarray
    without_temperature: np.ndarray
    method: str = "leave_one_out"
    metadata: dict = field(default_factory=dict)

    @property
    def ensemble(self) -> pd.DataFrame:
        """Contribution (with minus without) per year and member, K."""
        return self._frame(self.with_temperature - self.without_temperature)

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
        temps = (
            self.with_temperature
            if self.method == "leave_one_out"
            else self.without_temperature
        )
        in_base = (self.years >= 1850) & (self.years <= 1901)
        weights = np.ones(in_base.sum())
        weights[[0, -1]] = 0.5
        baseline = np.average(temps[in_base], axis=0, weights=weights)
        return _quantile_frame(self._frame(temps - baseline), quantiles)

    def warming_rate(self, window: int = 10) -> pd.DataFrame:
        """How fast the contribution is changing, K per year, per member.

        The value for year Y covers the `window` years up to Y, so it uses
        only years that have already happened. Near zero means the entity has
        stopped adding warming.
        """
        return _neutrality.warming_rate(self.ensemble, window)

    def neutrality(
        self,
        from_year: int,
        rule: str = "peak",
        tolerance: float = 0.0,
        window: int = 10,
    ) -> _neutrality.NeutralityResult:
        """The first year from which this entity adds no more warming.

        rule "peak": the contribution never rises again.
        rule "hold": the contribution never again goes above its `from_year`
        level. Both are judged per ensemble member and must hold for every
        later year, so a relapse does not count.
        """
        return _neutrality.neutrality(self.ensemble, from_year, rule, tolerance, window)

    def plot(self, ax=None, color: str = "C0", start_year: int | None = None):
        """Median contribution with the 5-95 % range shaded. Returns the Axes.

        By default the plot starts 10 years before the first emission year
        (when known), so the flat pre-emission period does not dominate.
        """
        import matplotlib.pyplot as plt

        if ax is None:
            _, ax = plt.subplots(figsize=(8, 4.5))
        if start_year is None:
            first = self.metadata.get("first_emission_year")
            start_year = (
                self.years[0] if first is None else max(first - 10, self.years[0])
            )
        s = self.summary().loc[start_year:]
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
        ax.set_xlim(start_year, self.years[-1])
        ax.legend(frameon=False)
        return ax

    def __repr__(self) -> str:
        gases = ", ".join(self.metadata.get("species", {})) or "unknown gases"
        median_end = float(np.median(self.ensemble.iloc[-1]))
        return (
            f"ContributionResult({gases} on {self.metadata.get('background', '?')}, "
            f"{self.method}, {len(self.members)} members, "
            f"years {self.years[0]}-{self.years[-1]}, "
            f"median contribution in {self.years[-1]}: {median_end:.3g} K)"
        )

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
