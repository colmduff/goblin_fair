"""When does an entity stop adding warming?

An entity is *neutral* from a year on if its own warming contribution stops
rising. Two rules, both judged per ensemble member:

- "peak": the contribution never rises again (its warming rate stays at or
  below `tolerance`, in K per year).
- "hold": the contribution never again goes above its level in `from_year`
  (plus `tolerance`, in K).

Both return the first year from which the rule holds for every later year up to
the end of the run, so a later relapse does not count as neutral.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

RULES = ("peak", "hold")


@dataclass(frozen=True)
class NeutralityResult:
    """The year each ensemble member says the entity stopped adding warming."""

    years: pd.Series  # member -> year, NaN where it never happens
    rule: str
    from_year: int
    tolerance: float
    window: int
    end_year: int

    @property
    def share_reached(self) -> float:
        """Fraction of members that reach neutrality before the run ends."""
        return float(self.years.notna().mean())

    def by_share(self, share: float = 0.5) -> int | None:
        """Year by which this share of members is neutral, or None if never.

        `by_share(0.5)` is the median year, counting members that never get
        there, so it is None when fewer than half of them do.
        """
        if not 0 < share <= 1:
            raise ValueError(f"share must be between 0 and 1, got {share!r}")
        ordered = np.sort(self.years.to_numpy(dtype=float))
        position = int(np.ceil(share * ordered.size)) - 1
        year = ordered[position]
        return None if np.isnan(year) else int(year)

    def summary(self) -> dict:
        """One row describing the result, for tables and reports."""
        return {
            "rule": self.rule,
            "from_year": self.from_year,
            "tolerance": self.tolerance,
            "window": self.window,
            "share_reached": self.share_reached,
            "p50": self.by_share(0.5),
            "p90": self.by_share(0.9),
        }

    def __repr__(self) -> str:
        p50 = self.by_share(0.5)
        when = "not reached" if p50 is None else f"half of members by {p50}"
        return (
            f"NeutralityResult(rule={self.rule!r}, from {self.from_year}, "
            f"{self.share_reached:.0%} of members neutral by {self.end_year}, {when})"
        )


def warming_rate(contribution: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Rate of change of the contribution, K per year, per member.

    Trailing: the value for year Y covers the `window` years up to Y, so it
    only uses years that have already happened. The first `window` years are
    empty for that reason.
    """
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError(f"window must be a whole number of years >= 1, got {window!r}")
    values = contribution.to_numpy(dtype=float)
    if window >= values.shape[0]:
        raise ValueError(
            f"window of {window} years needs a longer run: "
            f"the contribution covers {values.shape[0]} years"
        )
    rate = np.full_like(values, np.nan)
    rate[window:] = (values[window:] - values[:-window]) / window
    return pd.DataFrame(rate, index=contribution.index, columns=contribution.columns)


def neutrality(
    contribution: pd.DataFrame,
    from_year: int,
    rule: str = "peak",
    tolerance: float = 0.0,
    window: int = 10,
) -> NeutralityResult:
    """First year from which the entity adds no more warming, per member."""
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}; choose one of {', '.join(RULES)}")
    years = contribution.index.to_numpy(dtype=int)
    if not years[0] <= from_year <= years[-1]:
        raise ValueError(
            f"from_year must be inside the run ({years[0]}..{years[-1]}), "
            f"got {from_year}"
        )
    if rule == "peak":
        test = warming_rate(contribution, window).to_numpy() <= tolerance
    else:
        pinned = contribution.loc[from_year].to_numpy()
        test = contribution.to_numpy() <= pinned + tolerance
    later = years >= from_year
    holds = _first_year_that_holds(test[later], years[later])
    return NeutralityResult(
        years=pd.Series(holds, index=contribution.columns, name="neutral_year"),
        rule=rule,
        from_year=int(from_year),
        tolerance=float(tolerance),
        window=int(window),
        end_year=int(years[-1]),
    )


def _first_year_that_holds(test: np.ndarray, years: np.ndarray) -> np.ndarray:
    """First year from which `test` (years × members) stays true to the end."""
    keeps_holding = np.flip(np.logical_and.accumulate(np.flip(test, axis=0), axis=0), 0)
    found = keeps_holding.any(axis=0)
    first = np.argmax(keeps_holding, axis=0)
    return np.where(found, years[first], np.nan)
