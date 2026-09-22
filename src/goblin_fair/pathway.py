"""Work backwards: what emissions keep an entity's warming flat?

The forward question is "these emissions cause this much warming". This module
answers the reverse: "to stop adding warming from year X on, how fast does this
entity have to cut?"

The answer is one number: a steady percentage cut each year. A steady rate is
used on purpose. Solving each year on its own gives a jagged path, because
methane's warming peaks about six years after the emission and a year-by-year
solve swings up and down chasing it. Nobody can act on a saw-tooth.

The search runs FaIR itself at different cut rates and narrows in on the
smallest one that works (`goblin_fair.api.neutral_pathway`). Nothing here
assumes warming is proportional to emissions, so the answer needs no
correction afterwards.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def decline_path(
    emissions: np.ndarray, years: np.ndarray, from_year: int, rate: float
) -> np.ndarray:
    """The pathway that falls by `rate` (a fraction) every year from `from_year`.

    `rate=0.01` is a 1 % cut each year; a negative rate is growth. The cut
    starts in `from_year` itself, so `from_year` is the first year the entity
    acts. It has to be: the emissions of `from_year` set the warming of the
    year after it, so leaving them alone would put the target out of reach
    whenever warming is still rising.

    Earlier years keep the emissions they were given, and the level they are
    scaled from is the entity's own emissions in `from_year`.
    """
    years = np.asarray(years, dtype=int)
    out = np.asarray(emissions, dtype=float).copy()
    start = out[years == from_year]
    if start.size == 0:
        raise ValueError(f"from_year {from_year} is not one of the emission years")
    acting = years >= from_year
    out[acting] = start[0] * (1.0 - rate) ** (years[acting] - from_year + 1)
    return out


def overshoot(
    warming: np.ndarray, years: np.ndarray, from_year: int, by_year: int
) -> np.ndarray:
    """How far above its `from_year` level the warming still is from `by_year` on.

    Works on one warming curve or on a whole ensemble (years × members), and
    returns one number per member, in K. Zero or below means the entity has
    stopped adding warming by then and does not start again.

    Years between `from_year` and `by_year` are the transition and are not
    judged. Warming already in the pipeline keeps rising for a few years
    whatever the entity does, so demanding no rise from the very next year
    would force an immediate collapse to zero rather than a realistic cut.
    """
    years = np.asarray(years, dtype=int)
    warming = np.atleast_2d(np.asarray(warming, dtype=float).T).T
    pinned = warming[years == from_year][0]
    return warming[years >= by_year].max(axis=0) - pinned


# The search never goes beyond 20 % growth or a 60 % cut a year.
RATE_LIMITS = (-0.20, 0.60)


def solve_rate(
    overshoot_at: Callable[[float], float],
    bounds: tuple[float, float] = (0.0, 0.05),
    limits: tuple[float, float] = RATE_LIMITS,
    steps: int = 7,
) -> tuple[float, float, float]:
    """Smallest yearly cut whose overshoot is zero or below.

    `overshoot_at(rate)` runs the model and says how far above the line the
    warming still ends up. Cutting faster always means less warming, so the
    range is first widened until it holds the answer, then halved `steps`
    times. Returns the rate, and the range it is known to lie in.
    """
    low, high = bounds
    while overshoot_at(low) <= 0:  # already neutral: look for a gentler rate
        if low <= limits[0]:
            return limits[0], limits[0], limits[0]
        high, low = low, max(limits[0], low - (high - low) * 2)
    while overshoot_at(high) > 0:  # not enough: look for a harder cut
        if high >= limits[1]:
            return limits[1], limits[1], limits[1]
        low, high = high, min(limits[1], high + (high - low) * 2)
    for _ in range(steps):
        middle = (low + high) / 2
        if overshoot_at(middle) > 0:
            low = middle
        else:
            high = middle
    return high, low, high


@dataclass(frozen=True)
class NeutralPathway:
    """The emissions that keep an entity's warming flat, and how they compare.

    Attributes
    ----------
    decline : the yearly cut needed, in % per year, as p5 / p50 / p95 across
        ensemble members. p50 is the headline number. Each member's rate is
        read off the runs the search made; the search adds runs until every
        member has a rate that works and one that does not, so only a member
        beyond the limits (20 % growth, 60 % cut) is clipped. A rate so fast
        that the entity would out-emit the whole world counts as not neutral.
        `verification` lists the rates tried and whether the search hit a
        limit.
    emissions : the entity's emissions with the solved column replaced by the
        neutral pathway, in the units given. Feed it straight back into
        `temperature_contribution` to see the warming it causes.
    pathway : the neutral pathway itself, in the units given. `p50` is the
        headline path. `p5` and `p95` are quantiles of the *emissions*, so
        `p5` is the lowest path, which is the harshest cut — the opposite end
        from `decline["p5"]`, which is the gentlest rate.
    allowance : `pathway` minus the pathway you gave. Positive means the entity
        could emit more than planned and still add no warming; negative means it
        has to cut further.
    verification : what the final FaIR run actually did, including the share of
        ensemble members for which this pathway really is neutral.
    metadata : the choices behind the answer.
    """

    decline: dict
    emissions: pd.DataFrame
    pathway: pd.DataFrame
    allowance: pd.DataFrame
    member_declines: pd.Series
    verification: dict
    metadata: dict = field(default_factory=dict)

    def cumulative_allowance(self, to_year: int | None = None) -> pd.Series:
        """Extra (or missing) emissions added up from the pinned year, per quantile."""
        start = self.metadata["from_year"]
        end = self.allowance.index[-1] if to_year is None else to_year
        return self.allowance.loc[start:end].sum()

    def cut_by(self, year: int) -> float:
        """Total cut from the pinned year to `year`, in % (median member)."""
        start = self.metadata["from_year"]
        first = self.pathway["p50"].loc[start]
        return float(100 * (1 - self.pathway["p50"].loc[year] / first))

    def summary(self) -> dict:
        """The answer in one row: the cut needed, and how well it was verified."""
        end = int(self.metadata["by_year"])
        return {
            "solve": self.metadata["solve"],
            "from_year": self.metadata["from_year"],
            "background": self.metadata["background"],
            "decline_%_per_year": self.decline["p50"],
            "decline_p5_p95": (self.decline["p5"], self.decline["p95"]),
            f"cut_by_{end}_%": self.cut_by(end),
            "overshoot_mK": self.verification["overshoot_K"] * 1000,
            "pinned_mK": self.verification["pinned_K"] * 1000,
            "share_neutral": self.verification["share_neutral"],
        }

    def __repr__(self) -> str:
        end = int(self.metadata["by_year"])
        return (
            f"NeutralPathway({self.metadata['solve']} neutral from "
            f"{self.metadata['from_year']}: cut {self.decline['p50']:.2f} %/yr "
            f"(p5-p95 {self.decline['p5']:.2f}-{self.decline['p95']:.2f}), "
            f"{self.cut_by(end):.0f} % below by {end}, "
            f"neutral for {self.verification['share_neutral']:.0%} of members)"
        )
