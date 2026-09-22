"""Rebuild goblin_fair's bundled data from upstream sources.

Every upstream file is downloaded into the pooch cache and verified against a
known hash before use. Outputs go to src/goblin_fair/data/ and their SHA-256
values are printed for the checksum table in DATA_SOURCES.md, which documents
the provenance of each file.

Run: make data   (or: poetry run python scripts/build_data.py)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pooch
from scipy.interpolate import interp1d

from goblin_fair import _data

OUT = Path(__file__).resolve().parents[1] / "src" / "goblin_fair" / "data"

# FaIR repository, examples/data/calibrated_constrained_ensemble/, pinned to the
# last commit that changed that folder (2024-07-23).
FAIR_COMMIT = "28572bb00e40d73f83f3365395fe8bc3a1b60bb9"
FAIR_BASE = (
    "https://raw.githubusercontent.com/OMS-NetZero/FAIR/"
    f"{FAIR_COMMIT}/examples/data/calibrated_constrained_ensemble/"
)
FAIR_SHA256 = {
    "calibrated_constrained_parameters_calibration1.4.1.csv": (
        "7b6c5d9fa0b0b0d3eb47189bf5d63cbf77e752ddac682947abee5ff529206780"
    ),
    "species_configs_properties_calibration1.4.1.csv": (
        "42d04aa1a8f385cc53eae22beab26f857c535c5aa7dfdb98176d712bfc0c95a0"
    ),
    "volcanic_solar.csv": (
        "621b551dafa6ff0e5a789b94a81a12876d796832c0e15f627545af40d6de58e5"
    ),
}

# RCMIP protocol v5.1.0 emissions; the same URL and hash fair 2.2.4 pins in
# fair.io.fill_from_rcmip.
RCMIP_URL = (
    "https://rcmip-protocols-au.s3-ap-southeast-2.amazonaws.com/"
    "v5.1.0/rcmip-emissions-annual-means-v5-1-0.csv"
)
RCMIP_MD5 = "md5:4044106f55ca65b094670e7577eaf9b3"


def fetch_fair(name: str) -> Path:
    return Path(
        pooch.retrieve(FAIR_BASE + name, known_hash=f"sha256:{FAIR_SHA256[name]}")
    )


def rcmip_name(specie: str) -> str:
    """FaIR species name -> RCMIP variable suffix (as fair.io.fill_from_rcmip)."""
    special = {
        "CO2 FFI": "CO2|MAGICC Fossil and Industrial",
        "CO2 AFOLU": "CO2|MAGICC AFOLU",
    }
    return special.get(specie, specie.replace("-", ""))


def build_background(rcmip_csv: Path, species_csv: Path) -> pd.DataFrame:
    """World emissions of every FaIR emission species for the 8 SSPs.

    Written in fair's CSV format (scenario, region, variable, unit, timepoints)
    so FAIR.fill_from_pandas reads it and applies fair's own unit conversion.
    Values are interpolated exactly as fill_from_rcmip does: linear
    interpolation across RCMIP's gaps, then linear (extrapolating) onto the
    mid-year timepoints 1750.5..2500.5.
    """
    rc = pd.read_csv(rcmip_csv)
    rc = rc[(rc["Region"] == "World") & rc["Scenario"].isin(_data.BACKGROUNDS)]
    props = pd.read_csv(species_csv, index_col=0)
    species = props.index[props["input_mode"] == "emissions"]
    year_cols = [str(y) for y in range(1750, 2501)]
    timepoints = np.arange(1750.5, 2501.5)
    rows = []
    for scenario in _data.BACKGROUNDS:
        for specie in species:
            sel = rc[
                (rc["Scenario"] == scenario)
                & rc["Variable"].str.endswith("|" + rcmip_name(specie))
            ]
            if len(sel) != 1:
                raise RuntimeError(
                    f"{scenario}/{specie}: expected 1 RCMIP row, got {len(sel)}"
                )
            values = (
                sel[year_cols].astype(float).interpolate(axis=1).to_numpy().squeeze()
            )
            notnan = ~np.isnan(values)
            values = interp1d(
                timepoints[notnan],
                values[notnan],
                fill_value="extrapolate",
                bounds_error=False,
            )(timepoints)
            row = {
                "scenario": scenario,
                "region": "World",
                "variable": specie,
                "unit": sel["Unit"].iloc[0],
            }
            row.update({f"{t:.1f}": v for t, v in zip(timepoints, values, strict=True)})
            rows.append(row)
    return pd.DataFrame(rows)


def build_forcing(volcanic_solar_csv: Path) -> pd.DataFrame:
    """Solar and Volcanic forcing collapsed to one series each, on integer years.

    The upstream file repeats identical rows for 7 scenarios and has uneven
    year spacing at the end; values are linearly interpolated onto 1750..2500
    (as fair.io.fill_from_pandas would do onto timebounds).
    """
    vs = pd.read_csv(volcanic_solar_csv, encoding="utf-8-sig")
    meta = ("Scenario", "Variable", "Region", "Unit")
    year_cols = [c for c in vs.columns if c not in meta]
    years_in = np.array(year_cols, dtype=float)
    years_out = np.arange(_data.START_YEAR, _data.MAX_END_YEAR + 1)
    out = pd.DataFrame(index=pd.Index(years_out, name="year"))
    for var in ("Solar", "Volcanic"):
        block = vs.loc[vs["Variable"] == var, year_cols].astype(float)
        if not (block.nunique(axis=0) == 1).all():
            raise RuntimeError(f"{var} forcing differs between scenarios")
        out[var] = np.interp(years_out, years_in, block.iloc[0].to_numpy())
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    params = fetch_fair("calibrated_constrained_parameters_calibration1.4.1.csv")
    species = fetch_fair("species_configs_properties_calibration1.4.1.csv")
    volcanic_solar = fetch_fair("volcanic_solar.csv")
    rcmip = Path(pooch.retrieve(RCMIP_URL, known_hash=RCMIP_MD5))

    shutil.copyfile(params, OUT / _data.PARAMETERS_FILE)
    shutil.copyfile(species, OUT / _data.SPECIES_FILE)
    build_forcing(volcanic_solar).to_csv(OUT / _data.FORCING_FILE)
    build_background(rcmip, species).to_csv(OUT / _data.BACKGROUND_FILE, index=False)

    print("| file | sha256 |\n|---|---|")
    for name in _data.DATA_FILES:
        print(f"| `{name}` | `{_data.file_sha256(OUT / name)}` |")


if __name__ == "__main__":
    main()
