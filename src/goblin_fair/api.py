"""Public entry points."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

import pandas as pd

from goblin_fair import _data, engine
from goblin_fair.emissions import FAIR_UNITS, prepare_emissions
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
) -> ContributionResult:
    """Global surface temperature change caused by `emissions`.

    Runs the FaIR calibrated ensemble on a background scenario twice in one
    go, once as it is and once with `emissions` added, and returns the
    difference for every ensemble member.

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

    Returns
    -------
    ContributionResult
    """
    if background not in _data.BACKGROUNDS:
        raise ValueError(
            f"unknown background {background!r}; "
            f"choose one of {', '.join(_data.BACKGROUNDS)}"
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

    out = engine.run_pair(prepared, background, end_year, members)

    from goblin_fair import __version__

    metadata = {
        "goblin_fair_version": __version__,
        "fair_version": engine.fair_version(),
        "calibration": _data.CALIBRATION_VERSION,
        "background": background,
        "background_source": _data.BACKGROUND_SOURCE,
        "end_year": end_year,
        "n_members": len(out.members),
        "species": {specie: FAIR_UNITS[specie] for specie in prepared.columns},
        "first_emission_year": int(prepared.index[0]),
        "last_emission_year": int(prepared.index[-1]),
        "input_units": units if isinstance(units, str) else dict(units),
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return ContributionResult(
        out.years, out.members, out.background, out.perturbed, metadata
    )
