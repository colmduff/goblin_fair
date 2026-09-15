"""Validate user emissions and convert them to the species and units FaIR expects."""

from __future__ import annotations

import re
import warnings
from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_fair._data import START_YEAR

# user column (upper-cased) -> FaIR species
_COLUMN_TO_SPECIE = {
    "CO2": "CO2 FFI",
    "CO2_FFI": "CO2 FFI",
    "CO2_AFOLU": "CO2 AFOLU",
    "CH4": "CH4",
    "N2O": "N2O",
}
_SPECIE_ORDER = ("CO2 FFI", "CO2 AFOLU", "CH4", "N2O")

# What each species is converted to (FaIR's native emissions units).
FAIR_UNITS = {
    "CO2 FFI": "Gt CO2/yr",
    "CO2 AFOLU": "Gt CO2/yr",
    "CH4": "Mt CH4/yr",
    "N2O": "Mt N2O/yr",
}
_TONNES = {"t": 1.0, "kt": 1e3, "Mt": 1e6, "Gt": 1e9}

_EQUIVALENT = re.compile(r"co2[\s_-]*eq?|gwp", re.IGNORECASE)
_EQUIVALENT_MSG = (
    "goblin_fair needs gas-specific emissions (the mass of CO2, CH4 and N2O "
    "separately), not CO2-equivalent or GWP-weighted totals, because FaIR models "
    "each gas's own lifetime and warming effect"
)


def prepare_emissions(
    emissions: pd.DataFrame,
    units: str | Mapping[str, str] = "kt",
    end_year: int = 2100,
) -> pd.DataFrame:
    """Return emissions indexed by year, with FaIR species columns in FaIR units.

    Columns (case-insensitive): CO2, or CO2_FFI and/or CO2_AFOLU; CH4; N2O.
    CO2 on its own is treated as fossil (CO2_FFI). Values are the mass of the
    gas itself per year; negative values (removals) are allowed.

    `units` is one of "t", "kt", "Mt", "Gt", or a dict of those per column.
    Years must be whole, strictly increasing and within 1750..end_year-1.
    Missing years inside the range count as zero additional emissions.
    """
    if not isinstance(emissions, pd.DataFrame):
        raise ValueError("emissions must be a pandas DataFrame indexed by year")
    if emissions.shape[1] == 0:
        raise ValueError("emissions must have at least one gas column")

    labels = [str(c) for c in emissions.columns]
    names = [label.strip().upper() for label in labels]
    for label in labels:
        if _EQUIVALENT.search(label):
            raise ValueError(f"column {label!r}: {_EQUIVALENT_MSG}")
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate columns after ignoring case: {dupes}")
    unknown = [
        lab for lab, n in zip(labels, names, strict=True) if n not in _COLUMN_TO_SPECIE
    ]
    if unknown:
        raise ValueError(
            f"unsupported columns {unknown}; use CO2 (or CO2_FFI / CO2_AFOLU), CH4, N2O"
        )
    if "CO2" in names and {"CO2_FFI", "CO2_AFOLU"} & set(names):
        raise ValueError("give either CO2 or CO2_FFI/CO2_AFOLU, not both")

    unit_for = _resolve_units(units, names)
    years = _validate_years(emissions.index, end_year)

    out = pd.DataFrame(index=pd.Index(years, name="year"))
    for position, (label, name) in enumerate(zip(labels, names, strict=True)):
        column = emissions.iloc[:, position]
        if not pd.api.types.is_numeric_dtype(column) or pd.api.types.is_bool_dtype(
            column
        ):
            raise ValueError(f"column {label!r} must be numeric")
        values = column.to_numpy(dtype=float)
        if np.isnan(values).any():
            first_bad = int(years[np.isnan(values)][0])
            raise ValueError(
                f"column {label!r} has a missing value in year {first_bad}"
            )
        specie = _COLUMN_TO_SPECIE[name]
        target_prefix = FAIR_UNITS[specie].split()[0]
        out[specie] = values * _TONNES[unit_for[name]] / _TONNES[target_prefix]
    return out[[s for s in _SPECIE_ORDER if s in out.columns]]


def _resolve_units(units: str | Mapping[str, str], names: list[str]) -> dict[str, str]:
    if isinstance(units, str):
        mapping = {name: units for name in names}
    else:
        mapping = {str(k).strip().upper(): v for k, v in units.items()}
        missing = [name for name in names if name not in mapping]
        if missing:
            raise ValueError(f"units not given for columns {missing}")
    for name in names:
        unit = mapping[name]
        if _EQUIVALENT.search(str(unit)):
            raise ValueError(f"units for {name!r}: {_EQUIVALENT_MSG}")
        if unit not in _TONNES:
            raise ValueError(
                f"units for {name!r} must be one of t, kt, Mt, Gt; got {unit!r}"
            )
    return mapping


def _validate_years(index: pd.Index, end_year: int) -> np.ndarray:
    try:
        raw = np.asarray(index, dtype=float)
    except (TypeError, ValueError):
        raise ValueError("emissions must be indexed by years (integers)") from None
    if np.any(raw != np.round(raw)):
        raise ValueError("emissions index must be whole years")
    years = raw.astype(int)
    if np.any(np.diff(years) <= 0):
        raise ValueError(
            "emissions years must be strictly increasing with no duplicates"
        )
    last = end_year - 1
    if years[0] < START_YEAR or years[-1] > last:
        raise ValueError(
            f"emissions years must be within {START_YEAR}..{last}: emissions in a "
            "year first affect temperature at the start of the next year, so raise "
            "end_year to include later years"
        )
    if np.any(np.diff(years) > 1):
        warnings.warn(
            "emissions years have gaps; missing years are treated as zero "
            "additional emissions (no interpolation)",
            UserWarning,
            stacklevel=3,
        )
    return years
