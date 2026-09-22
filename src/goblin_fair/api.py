"""Public entry points."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from goblin_fair import _data, engine, pathway
from goblin_fair.emissions import (
    _TONNES,
    FAIR_UNITS,
    _canonical_name,
    prepare_emissions,
    specie_of,
)
from goblin_fair.results import ContributionResult


def list_backgrounds() -> list[str]:
    """Names of the available background scenarios (RCMIP v5.1.0 SSPs)."""
    return list(_data.BACKGROUNDS)


def temperature_contribution(
    emissions: pd.DataFrame,
    units: str | Mapping[str, str] = "kt",
    background: str = "ssp245",
    end_year: int = 2100,
    members: None | int | Sequence[int] = None,
    method: str = "leave_one_out",
) -> ContributionResult:
    """Global surface temperature change caused by `emissions`.

    Runs the FaIR calibrated ensemble on a background scenario twice in one
    go, with and without `emissions`, and returns the difference for every
    ensemble member.

    Parameters
    ----------
    emissions : pandas.DataFrame
        Indexed by year. Columns CO2 (or CO2_FFI and/or CO2_AFOLU), CH4, N2O,
        as the mass of each gas per year. Years missing from the index count
        as zero additional emissions.
    units : str or dict, default "kt"
        "t", "kt", "Mt" or "Gt", or a dict of those per column.
    background : str, default "ssp245"
        One of list_backgrounds().
    end_year : int, default 2100
        Last year simulated, 1902..2500. Emission years must be before it.
    members : None, int or list of int, default None
        None for all 841 calibrated ensemble members, an int N for the first
        N (quicker, for exploring), or a list of member ids.
    method : {"leave_one_out", "add"}, default "leave_one_out"
        "leave_one_out" attributes warming to an emitter that is already part
        of the background (a country, a sector): the SSP world minus the SSP
        world without `emissions`. "add" is for extra emissions that are not
        in the background (a new project): the SSP plus `emissions` minus
        the SSP.

    Returns
    -------
    ContributionResult
    """
    if background not in _data.BACKGROUNDS:
        raise ValueError(
            f"unknown background {background!r}; "
            f"choose one of {', '.join(_data.BACKGROUNDS)}"
        )
    if method not in engine.METHODS:
        raise ValueError(
            f"unknown method {method!r}; choose one of {', '.join(engine.METHODS)}"
        )
    if isinstance(end_year, bool) or not isinstance(end_year, int):
        raise ValueError(f"end_year must be an int, got {end_year!r}")
    if not _data.MIN_END_YEAR <= end_year <= _data.MAX_END_YEAR:
        raise ValueError(
            f"end_year must be between {_data.MIN_END_YEAR} and "
            f"{_data.MAX_END_YEAR}, got {end_year}"
        )
    prepared = prepare_emissions(emissions, units=units, end_year=end_year)
    _data.load_parameters(members)  # validate before the expensive run

    out = engine.run_pair(prepared, background, end_year, members, method)

    from goblin_fair import __version__

    metadata = {
        "goblin_fair_version": __version__,
        "fair_version": engine.fair_version(),
        "calibration": _data.CALIBRATION_VERSION,
        "method": method,
        "background": background,
        "background_source": _data.BACKGROUND_SOURCE,
        "end_year": end_year,
        "n_members": len(out.members),
        "species": {
            column: FAIR_UNITS[specie_of(column)] for column in prepared.columns
        },
        "streams": list(prepared.columns),
        "first_emission_year": int(prepared.index[0]),
        "last_emission_year": int(prepared.index[-1]),
        "input_units": units if isinstance(units, str) else dict(units),
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return ContributionResult(
        out.years, out.members, out.with_, out.without, method, metadata
    )


def neutral_pathway(
    emissions: pd.DataFrame,
    solve: str,
    from_year: int,
    units: str | Mapping[str, str] = "kt",
    background: str = "ssp245",
    end_year: int = 2100,
    members: None | int | Sequence[int] = None,
    by_year: int | None = None,
    steps: int = 7,
) -> pathway.NeutralPathway:
    """How fast must this entity cut, to stop adding warming from `from_year`?

    This is `temperature_contribution` the other way round. Instead of asking
    what warming a pathway causes, it asks what pathway keeps the entity's
    warming from going above its `from_year` level again. The answer is a
    steady percentage cut per year, plus the emissions pathway it implies.
    Everything except the `solve` column is left exactly as given.

    It works by running FaIR at different cut rates and narrowing in on the
    smallest one that works, so every number it reports comes from a real run.

    Parameters
    ----------
    emissions : pandas.DataFrame
        The entity's emissions, as for `temperature_contribution`. Include its
        history: methane's warming builds over about 30 years, so start the
        series well before `from_year`, or the answer will come out too strict.
    solve : str
        The column to solve for, e.g. "CH4" or "CH4:biogenic".
    from_year : int
        The year whose warming level must not be exceeded, and the first year
        the entity acts. Must be one of the emission years.
    by_year : int, optional
        The year by which the warming must be back at (or below) that level,
        and stay there. Defaults to the last emission year. Between the two
        years warming may still rise: that part is already in the pipeline.
    units, background, end_year, members :
        As for `temperature_contribution`.
    steps : int, default 7
        How many times the search halves its range. Each step is one FaIR run,
        and 7 steps pin the rate down to about 0.04 % a year.

    Returns
    -------
    NeutralPathway

    Examples
    --------
    >>> out = gf.neutral_pathway(ie, solve="CH4", from_year=2025)   # doctest: +SKIP
    >>> out.decline["p50"]        # % a year   # doctest: +SKIP
    >>> out.cut_by(2050)          # % below 2025 by 2050   # doctest: +SKIP
    """
    prepared = prepare_emissions(emissions, units=units, end_year=end_year)
    wanted = _canonical_name(solve)
    column = _prepared_name(wanted)
    if column not in prepared.columns:
        raise ValueError(
            f"cannot solve for {solve!r}: the emissions have {list(prepared.columns)}"
        )
    years = prepared.index.to_numpy(dtype=int)
    if not years[0] <= from_year <= years[-1]:
        raise ValueError(
            f"from_year must be one of the emission years "
            f"({years[0]}..{years[-1]}), got {from_year}"
        )
    by_year = int(years[-1]) if by_year is None else int(by_year)
    if not from_year < by_year <= years[-1]:
        raise ValueError(
            f"by_year must be after from_year and no later than {years[-1]}, "
            f"got {by_year}"
        )
    given = prepared[column].to_numpy()
    seen: dict[float, np.ndarray | None] = {}
    base_members: np.ndarray | None = None

    def contribution_at(rate: float) -> np.ndarray | None:
        """Warming caused by the entity at this rate (years x members).

        None means the rate is impossible: growth so fast that the entity
        would emit more than the whole world. That can only happen while the
        search tries growth (a negative rate); at any other rate the same
        error means bad input, so it is raised.
        """
        key = round(float(rate), 6)
        if key not in seen:
            trial = prepared.copy()
            trial[column] = pathway.decline_path(given, years, from_year, key)
            try:
                run = engine.run_pair(
                    trial, background, end_year, members, "leave_one_out"
                )
            except ValueError as err:
                if key >= 0 or "negative global" not in str(err):
                    raise
                seen[key] = None
                return None
            nonlocal base_members
            base_members = run.members
            seen[key] = (run.with_ - run.without)[np.isin(run.years, years)]
        return seen[key]

    def overshoot_at(rate: float) -> float:
        """How far the median member is still above the line. Zero or less passes."""
        curve = contribution_at(rate)
        if curve is None:  # bigger than the world: certainly not neutral
            return float("inf")
        return float(np.median(pathway.overshoot(curve, years, from_year, by_year)))

    rate, low, high = pathway.solve_rate(overshoot_at, steps=steps)

    # Every member sees the same pathway but has its own climate, so each one
    # needs its own rate. Every run tried is reused to find where each member's
    # overshoot crosses zero. An impossible rate is too much warming for all.
    def member_overshoots() -> dict[float, np.ndarray]:
        return {
            r: np.full(len(base_members), np.inf)
            if curve is None
            else pathway.overshoot(curve, years, from_year, by_year)
            for r, curve in seen.items()
        }

    # The search only needs the median member, so some members may have no
    # rate on one side of their answer (e.g. when 0 % works for the median,
    # only growth is tried). Try a step further out until every member has a
    # rate that works and one that does not, or the limits are reached.
    tried = member_overshoots()
    gentlest, harshest = pathway.RATE_LIMITS
    for _ in range(4):
        rates = sorted(tried)
        more_cut = (tried[rates[-1]] > 0).any() and rates[-1] < harshest
        less_cut = (tried[rates[0]] <= 0).any() and rates[0] > gentlest
        if not (more_cut or less_cut):
            break
        if more_cut:
            contribution_at(min(harshest, rates[-1] + 0.05))
        if less_cut:
            contribution_at(max(gentlest, rates[0] - 0.05))
        tried = member_overshoots()
    per_member = _member_rates(tried)

    final = contribution_at(rate)
    pinned = float(np.median(final[years == from_year][0]))
    final_overshoot = pathway.overshoot(final, years, from_year, by_year)
    factor = _to_user_units(column, units)
    member_paths = np.stack(
        [pathway.decline_path(given, years, from_year, r) for r in per_member], axis=1
    )
    quantiles = _quantiles(member_paths / factor, years)
    quantiles["p50"] = pathway.decline_path(given, years, from_year, rate) / factor
    source = _given_column(emissions, wanted)
    out = emissions.copy()
    out[source] = quantiles["p50"].to_numpy()
    return pathway.NeutralPathway(
        decline={
            "p5": 100 * float(np.quantile(per_member, 0.05)),
            "p50": 100 * rate,
            "p95": 100 * float(np.quantile(per_member, 0.95)),
        },
        emissions=out,
        pathway=quantiles,
        allowance=quantiles.sub(emissions[source].to_numpy(), axis=0),
        member_declines=pd.Series(
            100 * per_member,
            index=pd.Index(base_members, name="member"),
            name="decline_%_per_year",
        ),
        verification={
            "overshoot_K": float(np.median(final_overshoot)),
            "pinned_K": pinned,
            "share_neutral": float((final_overshoot <= 0).mean()),
            "rate_known_within": 100 * (high - low),
            "search_hit_limit": bool(low == high),
            "runs": len(seen),
            "rates_tried": sorted(100 * r for r in seen),
        },
        metadata={
            "solve": wanted,
            "from_year": int(from_year),
            "by_year": by_year,
            "units": units if isinstance(units, str) else dict(units),
            "background": background,
            "end_year": end_year,
            "n_members": final.shape[1],
            "rule": "hold",
        },
    )


def _member_rates(tried: dict) -> np.ndarray:
    """The cut each member needs, read off every rate the search tried.

    For each member, find the gentlest rate that worked and the harshest that
    did not, then interpolate between them.
    """
    rates = np.array(sorted(tried))
    overs = np.stack([tried[r] for r in rates])  # rates x members
    out = np.full(overs.shape[1], rates[-1], dtype=float)
    for member in range(overs.shape[1]):
        column = overs[:, member]
        works = np.flatnonzero(column <= 0)
        if works.size == 0:
            continue  # even the harshest cut tried was not enough
        first = works[0]
        if first == 0:
            out[member] = rates[0]  # even the gentlest rate tried was enough
            continue
        before, after = column[first - 1], column[first]
        if not np.isfinite(before):
            out[member] = rates[first]  # next to an impossible rate: no slope
            continue
        span = before - after
        share = 0.0 if span == 0 else before / span
        out[member] = rates[first - 1] + share * (rates[first] - rates[first - 1])
    return out


def _prepared_name(canonical: str) -> str:
    """User spelling ("CH4:biogenic") -> the prepared column name."""
    from goblin_fair.emissions import _COLUMN_TO_SPECIE, label_of

    gas = _COLUMN_TO_SPECIE.get(specie_of(canonical))
    if gas is None:
        return canonical
    label = label_of(canonical)
    return gas if label is None else f"{gas}:{label}"


def _given_column(emissions: pd.DataFrame, wanted: str) -> str:
    for column in emissions.columns:
        if _canonical_name(str(column)) == wanted:
            return column
    raise ValueError(f"cannot solve for {wanted!r}: no such column")


def _to_user_units(column, units) -> float:
    unit = units if isinstance(units, str) else dict(units)[column]
    prefix = FAIR_UNITS[specie_of(column)].split()[0]
    return _TONNES[unit] / _TONNES[prefix]


def _quantiles(values, years) -> pd.DataFrame:
    qs = np.quantile(values, [0.05, 0.5, 0.95], axis=1).T
    return pd.DataFrame(
        qs, index=pd.Index(years, name="year"), columns=["p5", "p50", "p95"]
    )
