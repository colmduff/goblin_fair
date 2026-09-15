"""Bundled model inputs: locations, loaders and checksums.

Provenance for every file is in data/DATA_SOURCES.md; rebuild them with
scripts/build_data.py.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

import pandas as pd

START_YEAR = 1750
MIN_END_YEAR = 1902  # the 1850-1900 baseline needs timebound 1901
MAX_END_YEAR = 2500

CALIBRATION_VERSION = "1.4.1"
BACKGROUND_SOURCE = "RCMIP v5.1.0"
BACKGROUNDS = (
    "ssp119",
    "ssp126",
    "ssp245",
    "ssp370",
    "ssp434",
    "ssp460",
    "ssp534-over",
    "ssp585",
)

PARAMETERS_FILE = "calibrated_constrained_parameters_1.4.1.csv"
SPECIES_FILE = "species_configs_properties_1.4.1.csv"
FORCING_FILE = "solar_volcanic_forcing.csv"
BACKGROUND_FILE = "background_emissions_rcmip_v5.1.0.csv"
DATA_FILES = (PARAMETERS_FILE, SPECIES_FILE, FORCING_FILE, BACKGROUND_FILE)

_DATA_DIR = Path(__file__).resolve().parent / "data"


def data_path(name: str) -> Path:
    """Absolute path of a bundled data file."""
    return _DATA_DIR / name


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _all_parameters() -> pd.DataFrame:
    return pd.read_csv(data_path(PARAMETERS_FILE), index_col=0)


def load_parameters(members: None | int | Sequence[int] = None) -> pd.DataFrame:
    """Calibrated parameter sets, one row per ensemble member.

    members: None for all 841; an int N for the first N; or a sequence of
    member ids (kept in the order given).
    """
    params = _all_parameters()
    if members is None:
        return params.copy()
    if isinstance(members, (bool, float, str)):
        raise ValueError(
            f"members must be None, an int or a list of member ids, got {members!r}"
        )
    if isinstance(members, int):
        if not 1 <= members <= len(params):
            raise ValueError(
                f"members must be between 1 and {len(params)}, got {members}"
            )
        return params.iloc[:members].copy()
    ids = list(members)
    if not ids:
        raise ValueError("members list is empty")
    unknown = [m for m in ids if m not in params.index]
    if unknown:
        raise ValueError(f"unknown members ids: {unknown[:5]}")
    return params.loc[ids].copy()


def load_forcing() -> pd.DataFrame:
    """Solar and volcanic effective radiative forcing (W m-2) on integer years."""
    return pd.read_csv(data_path(FORCING_FILE), index_col="year")


@lru_cache(maxsize=1)
def _all_backgrounds() -> pd.DataFrame:
    return pd.read_csv(data_path(BACKGROUND_FILE))


def load_background(background: str) -> pd.DataFrame:
    """Global emissions of every FaIR species for one SSP, in fair's CSV format."""
    if background not in BACKGROUNDS:
        raise ValueError(
            f"unknown background {background!r}; choose one of {', '.join(BACKGROUNDS)}"
        )
    df = _all_backgrounds()
    return df[df["scenario"] == background].reset_index(drop=True)
